# Universal Subtitles, universalsubtitles.org
# 
# Copyright (C) 2010 Participatory Culture Foundation
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see 
# http://www.gnu.org/licenses/agpl-3.0.html.

from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render_to_response, get_object_or_404, redirect
from django.template import RequestContext
from django.views.generic.list_detail import object_list
from videos.models import Video, VIDEO_TYPE_YOUTUBE, VIDEO_TYPE_HTML5, Action, TranslationLanguage, VideoCaptionVersion, TranslationVersion
from videos.forms import VideoForm, FeedbackForm, EmailFriendForm, UserTestResultForm
import widget
from django.contrib.sites.models import Site
from django.conf import settings
import simplejson as json
from videos.utils import get_pager
from django.contrib import messages
from django.db.models import Q
from widget.views import base_widget_params
from haystack.query import SearchQuerySet

def create(request):
    if request.method == 'POST':
        video_form = VideoForm(request.POST, label_suffix="")
        if video_form.is_valid():
            owner = request.user if request.user.is_authenticated() else None
            video_url = video_form.cleaned_data['video_url']
            video, created = Video.get_or_create_for_url(video_url, owner)
            if created:
                # TODO: log to activity feed
                pass
            return HttpResponseRedirect('{0}?subtitle_immediately=true'.format(reverse(
                    'videos:video', kwargs={'video_id':video.video_id})))            
            #if not video.owner or video.owner == request.user or video.allow_community_edits:
            #    return HttpResponseRedirect('{0}?autosub=true'.format(reverse(
            #            'videos:video', kwargs={'video_id':video.video_id})))
            #else:
            #    # TODO: better error page?
            #    return HttpResponse('You are not allowed to add transcriptions to this video.')
    else:
        video_form = VideoForm(label_suffix="")
    return render_to_response('videos/create.html', locals(),
                              context_instance=RequestContext(request))

def video(request, video_id):
    video = get_object_or_404(Video, video_id=video_id)
    video.view_count += 1
    video.save()
    # TODO: make this more pythonic, prob using kwargs
    context = widget.add_onsite_js_files({})
    context['video'] = video
    context['site'] = Site.objects.get_current()
    context['autosub'] = 'true' if request.GET.get('autosub', False) else 'false'
    context['translations'] = video.translationlanguage_set.all()
    context['widget_params'] = base_widget_params(request, {
                                'video_url': video.get_video_url()
                            })
    return render_to_response('videos/video.html', context,
                              context_instance=RequestContext(request))
                              
def video_list(request):
    from django.db.models import Count
    try:
        page = int(request.GET['page'])
    except (ValueError, TypeError, KeyError):
        page = 1
    qs = Video.objects.annotate(translation_count=Count('translationlanguage'))
    ordering = request.GET.get('o')
    order_type = request.GET.get('ot')
    extra_context = {}
    order_fields = ['translation_count', 'widget_views_count', 'subtitles_fetched_count']
    if ordering in order_fields and order_type in ['asc', 'desc']:
        qs = qs.order_by(('-' if order_type == 'desc' else '')+ordering)
        extra_context['ordering'] = ordering
        extra_context['order_type'] = order_type
    return object_list(request, queryset=qs, allow_empty=True,
                       paginate_by=50, page=page,
                       template_name='videos/video_list.html',
                       template_object_name='video',
                       extra_context=extra_context)

def actions_list(request):
    try:
        page = int(request.GET['page'])
    except (ValueError, TypeError, KeyError):
        page = 1    
    qs = Action.objects.all()
    
    extra_context = {}
    ordering = request.GET.get('o')
    order_type = request.GET.get('ot')    
    order_fields = ['user__username', 'created', 'video__video_id']
    if ordering in order_fields and order_type in ['asc', 'desc']:
        qs = qs.order_by(('-' if order_type == 'desc' else '')+ordering)
        extra_context['ordering'] = ordering
        extra_context['order_type'] = order_type
            
    return object_list(request, queryset=qs, allow_empty=True,
                       paginate_by=settings.ACTIVITIES_ONPAGE, page=page,
                       template_name='videos/actions_list.html',
                       template_object_name='action',
                       extra_context=extra_context)    

def feedback(request):
    output = dict(success=False)
    form = FeedbackForm(request.POST)
    if form.is_valid():
        form.send(request)
        output['success'] = True
    else:
        output['errors'] = form.get_errors()
    return HttpResponse(json.dumps(output), "text/javascript")

def email_friend(request):
    text = request.GET.get('text', '')
    link = request.GET.get('link', '')
    if link:
        text = link if not text else '%s\n%s' % (text, link) 
    initial = dict(message=text)
    if request.method == 'POST':
        form = EmailFriendForm(request.POST, auto_id="email_friend_id_%s", label_suffix="")
        if form.is_valid():
            form.send()
    else:
        form = EmailFriendForm(auto_id="email_friend_id_%s", initial=initial, label_suffix="")
    context = {
        'form': form
    }
    return render_to_response('videos/email_friend.html', context,
                              context_instance=RequestContext(request))

def demo(request):
    context = widget.add_onsite_js_files({})
    return render_to_response('demo.html', context,
                              context_instance=RequestContext(request))

def history(request, video_id):
    video = get_object_or_404(Video, video_id=video_id)
    context = widget.add_onsite_js_files({})

    qs = VideoCaptionVersion.objects.filter(video=video)   \
        .exclude(time_change=0, text_change=0)
    ordering, order_type = request.GET.get('o'), request.GET.get('ot')
    order_fields = {
        'date': 'datetime_started', 
        'user': 'user__username', 
        'note': 'note', 
        'time': 'time_change', 
        'text': 'text_change'
    }
    if ordering in order_fields and order_type in ['asc', 'desc']:
        qs = qs.order_by(('-' if order_type == 'desc' else '')+order_fields[ordering])
        context['ordering'], context['order_type'] = ordering, order_type

    context['video'] = video
    context['site'] = Site.objects.get_current()
    context['translations'] = TranslationLanguage.objects.filter(video=video)
    context['last_version'] = video.captions()
    context['widget_params'] = base_widget_params(request, {
                                'video_url': video.get_video_url()
                            })    
    return object_list(request, queryset=qs, allow_empty=True,
                       paginate_by=settings.REVISIONS_ONPAGE, 
                       page=request.GET.get('page', 1),
                       template_name='videos/history.html',
                       template_object_name='revision',
                       extra_context=context)      

def translation_history(request, video_id, lang):
    video = get_object_or_404(Video, video_id=video_id)
    language = get_object_or_404(TranslationLanguage, video=video, language=lang)
    context = widget.add_onsite_js_files({})
   
    qs = TranslationVersion.objects.filter(language=language) \
        .exclude(time_change=0, text_change=0)

    ordering, order_type = request.GET.get('o'), request.GET.get('ot')
    order_fields = {
        'date': 'datetime_started', 
        'user': 'user__username', 
        'note': 'note', 
        'time': 'time_change', 
        'text': 'text_change'
    }
    if ordering in order_fields and order_type in ['asc', 'desc']:
        qs = qs.order_by(('-' if order_type == 'desc' else '')+order_fields[ordering])
        context['ordering'], context['order_type'] = ordering, order_type 
    
    context['video'] = video
    context['language'] = language
    context['site'] = Site.objects.get_current()        
    context['translations'] = TranslationLanguage.objects.filter(video=video).exclude(pk=language.pk)
    context['last_version'] = video.translations(lang)
    context['widget_params'] = base_widget_params(request, {
                                'video_url': video.get_video_url()
                            })    
    return object_list(request, queryset=qs, allow_empty=True,
                       paginate_by=settings.REVISIONS_ONPAGE, 
                       page=request.GET.get('page', 1),
                       template_name='videos/translation_history.html',
                       template_object_name='revision',
                       extra_context=context) 

def revision(request, pk, cls=VideoCaptionVersion, tpl='videos/revision.html'):
    version = get_object_or_404(cls, pk=pk)
    context = widget.add_onsite_js_files({})
    context['video'] = version.video
    context['version'] = version
    context['next_version'] = version.next_version()
    context['prev_version'] = version.prev_version()
    context['widget_params'] = base_widget_params(request, {
                                'video_url': video.get_video_url()
                            })
    if cls == TranslationVersion:
        tpl = 'videos/translation_revision.html'
        context['latest_version'] = version.language.translations()
        context['is_writelocked'] = version.language.is_writelocked
    else:
        context['latest_version'] = version.video.captions()
        context['is_writelocked'] = version.video.is_writelocked
    return render_to_response(tpl, context,
                              context_instance=RequestContext(request))     

def last_revision(request, video_id):
    video = get_object_or_404(Video, video_id=video_id)
    
    context = widget.add_onsite_js_files({})
    context['video'] = video
    context['version'] = video.captions()
    context['translations'] = video.translationlanguage_set.all()
    context['widget_params'] = base_widget_params(request, {
                                'video_url': video.get_video_url()
                            })      
    return render_to_response('videos/last_revision.html', context,
                              context_instance=RequestContext(request))

def last_translation_revision(request, video_id, language_code):
    video = get_object_or_404(Video, video_id=video_id)
    language = video.translation_language(language_code)
    
    context = widget.add_onsite_js_files({})
    context['video'] = video
    context['version'] = video.translations(language_code)
    context['language'] = language
    context['translations'] = video.translationlanguage_set.exclude(pk=language.pk)
    context['widget_params'] = base_widget_params(request, {
                                'video_url': video.get_video_url()
                            })      
    return render_to_response('videos/last_revision.html', context,
                              context_instance=RequestContext(request))
    
@login_required
def rollback(request, pk, cls=VideoCaptionVersion):
    version = get_object_or_404(cls, pk=pk)
    user = request.user
    is_writelocked = version.video.is_writelocked if (cls == VideoCaptionVersion) else version.language.is_writelocked
    if is_writelocked:
        messages.error(request, 'Can not rollback now, because someone is editing subtitles.')
    elif not version.next_version():
        messages.error(request, message='Can not rollback to the last version')
    else:
        messages.success(request, message='Rollback was success')
        version = version.rollback(request.user)
    url_name = (cls == TranslationVersion) and 'translation_revision' or 'revision'
    return redirect('videos:%s' % url_name, pk=version.pk)

def diffing(request, first_pk, second_pk):
    first_version = get_object_or_404(VideoCaptionVersion, pk=first_pk)
    video = first_version.video
    second_version = get_object_or_404(VideoCaptionVersion, pk=second_pk, video=video)
    if second_version.datetime_started > first_version.datetime_started:
        first_version, second_version = second_version, first_version
    
    second_captions = dict([(item.caption_id, item) for item in second_version.captions()])
    captions = []
    for caption in first_version.captions():
        try:
            scaption = second_captions[caption.caption_id]
        except KeyError:
            scaption = None
            changed = dict(text=True, time=True)
        else:
            changed = {
                'text': (not caption.caption_text == scaption.caption_text), 
                'time': (not caption.start_time == scaption.start_time),
                'end_time': (not caption.end_time == scaption.end_time)
            }
        data = [caption, scaption, changed]
        captions.append(data)
        
    context = widget.add_onsite_js_files({})
    context['video'] = video
    context['captions'] = captions
    context['first_version'] = first_version
    context['second_version'] = second_version
    context['is_writelocked'] = video.is_writelocked
    context['history_link'] = reverse('videos:history', args=[video.video_id])
    context['latest_version'] = video.captions()
    context['widget1_params'] = base_widget_params(request, {
                                    'video_url': video.get_video_url()
                                })
    context['widget2_params'] = context['widget1_params']
    return render_to_response('videos/diffing.html', context,
                              context_instance=RequestContext(request)) 

def translation_diffing(request, first_pk, second_pk):
    first_version = get_object_or_404(TranslationVersion, pk=first_pk)
    language = first_version.language
    video = first_version.video
    second_version = get_object_or_404(TranslationVersion, pk=second_pk, language=language)
    if second_version.datetime_started > first_version.datetime_started:
        first_version, second_version = second_version, first_version
    
    second_captions = dict([(item.caption_id, item) for item in second_version.captions()])
    captions = []
    for caption in first_version.captions():
        try:
            scaption = second_captions[caption.caption_id]
        except KeyError:
            scaption = None
        changed = scaption and not caption.translation_text == scaption.translation_text 
        data = [caption, scaption, dict(text=changed, time=False, end_time=False)]
        captions.append(data)
        
    context = widget.add_onsite_js_files({})
    
    context['video'] = video
    context['captions'] = captions
    context['first_version'] = first_version
    context['second_version'] = second_version
    context['history_link'] = reverse('videos:translation_history', args=[video.video_id, language.language])
    context['is_writelocked'] = language.is_writelocked
    context['latest_version'] = language.translations()
    context['widget1_params'] = base_widget_params(request, {
                                    'video_url': video.get_video_url()
                                })
    context['widget2_params'] = context['widget1_params']    
    return render_to_response('videos/translation_diffing.html', context,
                              context_instance=RequestContext(request))

def test_form_page(request):
    if request.method == 'POST':
        form = UserTestResultForm(request.POST)
        if form.is_valid():
            form.save(request)
            messages.success(request, 'Thanks for your feedback.  It\'s a huge help to us as we improve the site.')
            return redirect('videos:test_form_page')
    else:
        form = UserTestResultForm()
    context = {
        'form': form           
    }
    return render_to_response('videos/test_form_page.html', context,
                              context_instance=RequestContext(request))

def search(request):
    q = request.REQUEST.get('q')
    print q
    try:
        page = int(request.GET['page'])
    except (ValueError, TypeError, KeyError):
        page = 1  
          
    if q:
        qs = SearchQuerySet().auto_query(q).highlight()
    else:
        qs = TranslationLanguage.objects.none()
        
    context = {
        'query': q
    }
    ordering, order_type = request.GET.get('o'), request.GET.get('ot')
    order_fields = {
        'title': 'title',
        'language': 'language'
    }
    if ordering in order_fields and order_type in ['asc', 'desc']:
        qs = qs.order_by(('-' if order_type == 'desc' else '')+order_fields[ordering])
        context['ordering'], context['order_type'] = ordering, order_type
        
    return object_list(request, queryset=qs, allow_empty=True,
                       paginate_by=30, page=page,
                       template_name='videos/search.html',
                       template_object_name='result',
                       extra_context=context)   
