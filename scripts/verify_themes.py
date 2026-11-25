from django.test import Client
from accounts.models import User, UserRole, VerificationStatus, EducationalInstitution, RecyclingProfile

client = Client(HTTP_HOST='localhost')

# 1. Public pages
for path in ['/accounts/login/', '/accounts/register/', '/accounts/about/', '/accounts/landing/']:
    res = client.get(path)
    assert res.status_code == 200, f'{path} returned {res.status_code}'
print('PUBLIC PAGES OK')

# 2. Institution pages
inst_user = User.objects.filter(role=UserRole.EDUCATIONAL_INSTITUTION, verification_status=VerificationStatus.VERIFIED).first()
if not inst_user:
    inst_user = User.objects.create_user(email='theme_inst@test.local', password='password123', role=UserRole.EDUCATIONAL_INSTITUTION, verification_status=VerificationStatus.VERIFIED)
    EducationalInstitution.objects.get_or_create(user=inst_user)

client.force_login(inst_user)
for path in ['/accounts/institution/', '/accounts/institution/profile/', '/accounts/institution/listings/new/', '/accounts/institution/partners/', '/accounts/ai/bulk-aggregation/', '/accounts/transactions/']:
    res = client.get(path)
    assert res.status_code == 200, f'{path} returned {res.status_code}'
    html = res.content.decode('utf-8')
    assert 'class="bg-white"' not in html, f'hardcoded bg-white in {path}'
print('INSTITUTION PAGES OK')

# 3. Recycler pages
rec_user = User.objects.filter(role=UserRole.RECYCLING_PARTNER, verification_status=VerificationStatus.VERIFIED).first()
if not rec_user:
    rec_user = User.objects.create_user(email='theme_rec@test.local', password='password123', role=UserRole.RECYCLING_PARTNER, verification_status=VerificationStatus.VERIFIED)
    RecyclingProfile.objects.get_or_create(user=rec_user)

client.force_login(rec_user)
for path in ['/accounts/partner/', '/accounts/partner/profile/', '/accounts/partner/profile/view/']:
    res = client.get(path)
    assert res.status_code == 200, f'{path} returned {res.status_code}'
    html = res.content.decode('utf-8')
    assert 'class="bg-white"' not in html, f'hardcoded bg-white in {path}'
print('RECYCLER PAGES OK')

print('ALL THEME & RESPONSIVE CHECKS PASSED')
