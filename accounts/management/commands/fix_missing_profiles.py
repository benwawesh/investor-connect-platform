from django.core.management.base import BaseCommand
from accounts.models import CustomUser, UserProfileExtension


class Command(BaseCommand):
    help = 'Create missing UserProfileExtension objects for existing users'

    def handle(self, *args, **options):
        fixed_count = 0

        for user in CustomUser.objects.all():
            if not hasattr(user, 'userprofileextension'):
                UserProfileExtension.objects.create(user=user)
                fixed_count += 1
                self.stdout.write(f'Created profile extension for {user.username}')

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created {fixed_count} missing profile extensions'
            )
        )