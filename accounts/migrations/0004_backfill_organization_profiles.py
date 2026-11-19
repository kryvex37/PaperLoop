from django.db import migrations


def create_missing_organization_profiles(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    EducationalInstitution = apps.get_model("accounts", "EducationalInstitution")
    RecyclingProfile = apps.get_model("accounts", "RecyclingProfile")
    database = schema_editor.connection.alias

    for user in User.objects.using(database).filter(role="institution").iterator():
        EducationalInstitution.objects.using(database).get_or_create(user_id=user.pk)
    for user in User.objects.using(database).filter(role="partner").iterator():
        RecyclingProfile.objects.using(database).get_or_create(user_id=user.pk)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0003_paperlisting_available_until_and_more"),
    ]

    operations = [
        migrations.RunPython(create_missing_organization_profiles, migrations.RunPython.noop),
    ]
