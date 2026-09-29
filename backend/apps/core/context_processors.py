from .models import SiteSettings


def payments_status(request):
    try:
        enabled = SiteSettings.payments_enabled()
    except Exception:
        enabled = False
    return {'payments_enabled': enabled}
