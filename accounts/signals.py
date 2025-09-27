from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import CustomUser, UserProfileExtension

@receiver(post_save, sender=CustomUser)
def create_user_profile_extension(sender, instance, created, **kwargs):
    """Automatically create UserProfileExtension when a user is created"""
    if created:
        UserProfileExtension.objects.create(user=instance)

@receiver(post_save, sender=CustomUser)
def ensure_user_profile_extension(sender, instance, **kwargs):
    """Ensure UserProfileExtension exists for existing users"""
    if not hasattr(instance, 'userprofileextension'):
        UserProfileExtension.objects.create(user=instance)