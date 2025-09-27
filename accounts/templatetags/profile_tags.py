from django import template
from django.urls import reverse

register = template.Library()

@register.inclusion_tag('accounts/profile_link.html')
def profile_link(user, text=None, show_avatar=True, css_class=""):
    """
    Renders a clickable profile link
    Usage: {% profile_link user %} or {% profile_link user "Custom Text" %}
    """
    return {
        'user': user,
        'text': text or user.get_full_name() or user.username,
        'show_avatar': show_avatar,
        'css_class': css_class,
        'profile_url': reverse('accounts:profile_detail', kwargs={'username': user.username})
    }