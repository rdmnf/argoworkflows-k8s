from django import template

from accounts.access import user_has_group, user_is_admin

register = template.Library()


@register.filter
def in_group(user, group_name):
    return user_has_group(user, group_name)


@register.filter
def is_admin(user):
    return user_is_admin(user)
