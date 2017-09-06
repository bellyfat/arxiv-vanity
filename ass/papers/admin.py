from django.contrib import admin
from django.contrib.admin.templatetags.admin_list import _boolean_icon
from django.template.defaultfilters import truncatechars
from django.utils.safestring import mark_safe
import json
from .models import Paper, Render, PaperIsNotRenderableError

class IsDownloadedListFilter(admin.SimpleListFilter):
    title = 'is downloaded'
    parameter_name = 'is_downloaded'

    def lookups(self, request, model_admin):
        return (
            ('1', 'Yes'),
            ('0', 'No'),
        )

    def queryset(self, request, queryset):
        if self.value() == '1':
            return queryset.downloaded()
        if self.value() == '0':
            return queryset.not_downloaded()


class HasSuccessfulRenderListFilter(admin.SimpleListFilter):
    title = 'has successful render'
    parameter_name = 'has_successful_render'

    def lookups(self, request, model_admin):
        return (
            ('1', 'Yes'),
            ('0', 'No'),
        )

    def queryset(self, request, queryset):
        if self.value() == '1':
            return queryset.has_successful_render()
        if self.value() == '0':
            return queryset.has_no_successful_render()


class PaperAdmin(admin.ModelAdmin):
    actions = ['download', 'render']
    list_display = ['arxiv_id', 'title', 'is_downloaded', 'is_renderable', 'has_successful_render']
    list_filter = [IsDownloadedListFilter, HasSuccessfulRenderListFilter]
    list_per_page = 250
    search_fields = ['arxiv_id', 'title']

    def is_downloaded(self, obj):
        return bool(obj.source_file.name)
    is_downloaded.boolean = True

    def is_renderable(self, obj):
        return obj.is_renderable()
    is_renderable.boolean = True

    def has_successful_render(self, obj):
        has_successful_render = obj.renders.succeeded().exists()
        s = _boolean_icon(has_successful_render)
        if not has_successful_render:
            try:
                last_failure = obj.renders.failed().latest()
            except Render.DoesNotExist:
                pass
            else:
                s += ' <a href="../render/{}">view failure</a>'.format(last_failure.id)
        return s
    has_successful_render.allow_tags = True

    def last_render_state(self, obj):
        try:
            render = obj.renders.latest()
        except Render.DoesNotExist:
            return ""
        return '<a href="../render/{}/">{}</a>'.format(render.id, render.state)
    last_render_state.allow_tags = True

    def download(self, request, queryset):
        for paper in queryset:
            paper.download()
    download.short_description = 'Download selected papers'

    def render(self, request, queryset):
        rendered = 0
        not_renderable = 0
        for paper in queryset:
            try:
                paper.render()
            except PaperIsNotRenderableError:
                not_renderable += 1
            else:
                rendered += 1
        s = "{} successfully rendered.".format(rendered)
        if not_renderable > 0:
            s += " {} not renderable.".format(not_renderable)
        self.message_user(request, s)
    render.short_description = 'Render selected papers'

admin.site.register(Paper, PaperAdmin)


class RenderAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'short_paper_title', 'state', 'short_container_id']
    list_filter = ['state']
    list_per_page = 250
    list_select_related = ['paper']

    # The fields except the ones we're formatting
    RENDER_FIELDS = [
        f.name for f in Render._meta.get_fields()
        if f.name not in ['container_logs', 'container_inspect']
    ] + ['formatted_container_logs', 'formatted_container_inspect']
    fields = RENDER_FIELDS
    readonly_fields = RENDER_FIELDS

    def formatted_container_logs(self, obj):
        return mark_safe("<pre>{}</pre>".format(obj.container_logs))
    formatted_container_logs.short_description = 'Container logs'

    def formatted_container_inspect(self, obj):
        formatted = json.dumps(obj.container_inspect, indent=2)
        return mark_safe("<pre>{}</pre>".format(formatted))
    formatted_container_inspect.short_description = 'Container inspect'

    def short_paper_title(self, obj):
        return truncatechars(obj.paper.title, 70)
    short_paper_title.short_description = 'Paper'

admin.site.register(Render, RenderAdmin)
