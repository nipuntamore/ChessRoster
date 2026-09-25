from django.core.management.base import BaseCommand
from tournaments.views import seed_demo_data
from django.test import RequestFactory


class Command(BaseCommand):
    help = 'Seeds demo tournament with 16 GMs and 3 rounds of results'

    def handle(self, *args, **options):
        factory = RequestFactory()
        request = factory.get('/tournaments/demo-seed/')
        # Create session and message support mock
        from django.contrib.sessions.middleware import SessionMiddleware
        from django.contrib.messages.middleware import MessageMiddleware
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(request)
        request.session.save()
        msg_middleware = MessageMiddleware(lambda req: None)
        msg_middleware.process_request(request)
        
        seed_demo_data(request)
        self.stdout.write(self.style.SUCCESS('Successfully seeded demo chess tournament data!'))
