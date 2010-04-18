#
# This file is part of my.gpodder.org.
#
# my.gpodder.org is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your
# option) any later version.
#
# my.gpodder.org is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero General Public
# License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with my.gpodder.org. If not, see <http://www.gnu.org/licenses/>.
#

from mygpo.api.basic_auth import require_valid_user
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden, Http404, HttpResponseNotAllowed
from mygpo.api.httpresponse import JsonResponse
from mygpo.exceptions import ParameterMissing
from django.shortcuts import get_object_or_404
from mygpo.api.sanitizing import sanitize_url
from mygpo.api.models import Device, Podcast, Episode
from mygpo.api.models.episodes import Chapter
from django.utils.translation import ugettext as _
from datetime import datetime, timedelta
from mygpo.log import log
from mygpo.utils import parse_time
import dateutil.parser
from django.views.decorators.csrf import csrf_exempt

try:
    #try to import the JSON module (if we are on Python 2.6)
    import json

    # Python 2.5 seems to have a different json module
    if not 'dumps' in dir(json):
        raise ImportError

except ImportError:
    # No JSON module available - fallback to simplejson (Python < 2.6)
    print "No JSON module available - fallback to simplejson (Python < 2.6)"
    import simplejson as json


@csrf_exempt
@require_valid_user
def chapters(request, username):
    print request.raw_post_data

    if request.method == 'POST':
        req = json.loads(request.raw_post_data)

        if not 'podcast' in req:
            return HttpResponseBadRequest('Podcast URL missing')

        if not 'episode' in req:
            return HttpResponseBadRequest('Episode URL missing')

        podcast_url = req.get('podcast', '')
        episode_url = req.get('episode', '')
        update_urls = []

        # podcast sanitizing
        s_podcast_url = sanitize_url(podcast_url)
        if s_podcast_url != podcast_url:
            req['podcast'] = s_podcast_url
            update_urls.append((podcast_url, s_podcast_url))

        # episode sanitizing
        s_episode_url = sanitize_url(episode_url, podcast=False, episode=True)
        if s_episode_url != episode_url:
            req['episode'] = s_episode_url
            update_urls.append((episode_url, s_episode_url))

        if (s_podcast_url != '') and (s_episode_url != ''):
            try:
                update_chapters(req, request.user)
            except ParameterMissing, e:
                return HttpResponseBadRequest(e)

        return JsonResponse({'update_url': update_url})

    elif request.method == 'GET':
        if not 'podcast' in request.GET:
            return HttpResponseBadRequest('podcast URL missing')

        if not 'episode' in request.GET:
            return HttpResponseBadRequest('Episode URL missing')

        podcast_url = request.GET['podcast']
        episode_url = request.GET['episode']

        podcast = Podcast.objects.get(url=sanitize_url(podcast_url))
        episode = Episode.objects.get(url=sanitize_url(episode_url, podcast=False, episode=True), podcast=podcast)
        chapters = []
        for c in Chapter.objects.filter(user=request.user, episode=episode).order_by('start'):
            chapters.append({
                'start': c.start,
                'end':   c.end,
                'label': c.label,
                'advertisement': c.advertisement,
                'timestamp': c.created,
                'device': c.device.uid
                })

        return JsonResponse(chapters)

    else:
        return HttpResponseNotAllowed(['GET', 'POST'])



def update_chapters(req, user):
    podcast, c = Podcast.objects.get_or_create(url=req['podcast'])
    episode, c = Episode.objects.get_or_create(url=req['episode'], podcast=podcast)

    device = None
    if 'device' in req:
        device, c = Device.objects.get_or_create(user=user, uid=req['device'], defaults = {'type': 'other', 'name': _('New Device')})

    timestamp = dateutil.parser.parse(req['timestamp']) if 'timestamp' in req else datetime.now()

    for c in req.get('chapters_add', []):
        if not 'start' in c:
            raise ParameterMissing('start parameter missing')
        start = parse_time(c['start'])

        if not 'end' in c:
            raise ParameterMissing('end parameter missing')
        end = parse_time(c['end'])

        label = c.get('label', '')
        adv = c.get('advertisement', False)


        Chapter.objects.create(
            user=user,
            episode=episode,
            device=device,
            created=timestamp,
            start=start,
            end=end,
            label=label,
            advertisement=adv)


    for c in req.get('chapters_remove', []):
        if not 'start' in c:
            raise ParameterMissing('start parameter missing')
        start = parse_time(c['start'])

        if not 'end' in c:
            raise ParameterMissing('end parameter missing')
        end = parse_time(c['end'])

        Chapter.objects.filter(
            user=user,
            episode=episode,
            start=start,
            end=end).delete()

