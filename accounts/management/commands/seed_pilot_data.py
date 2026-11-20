"""Idempotently seed synthetic Dhaka-area organizations and waste history."""
from datetime import timedelta
from decimal import Decimal

import numpy as np
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from accounts.models import (EducationalInstitution, PaperListing, RecyclingProfile,
                             User, UserRole, VerificationStatus, WasteRecord)


INSTITUTIONS = (
    ("Dhaka Central College", "Dhanmondi", 23.7370, 90.3980, 8500),
    ("Northside University", "Mirpur", 23.8060, 90.3680, 12000),
    ("Dhanmondi Girls College", "Dhanmondi", 23.7460, 90.3760, 4200),
    ("Uttara Science College", "Uttara", 23.8740, 90.3980, 5200),
    ("Motijheel Ideal School", "Motijheel", 23.7330, 90.4180, 11000),
    ("Old Dhaka Government School", "Old Dhaka", 23.7100, 90.4070, 3800),
    ("Banani International College", "Banani", 23.7930, 90.4060, 6700),
    ("Tejgaon Model College", "Tejgaon", 23.7620, 90.3990, 5900),
    ("Mohammadpur Public School", "Mohammadpur", 23.7660, 90.3580, 7400),
    ("Badda Community College", "Badda", 23.7800, 90.4250, 3600),
    ("Lalbagh Education Center", "Lalbagh", 23.7180, 90.3880, 3100),
    ("Farmgate College", "Farmgate", 23.7570, 90.3890, 9300),
)
RECYCLERS = (
    ("Dhaka Green Paper Recovery", "Dhanmondi, Mirpur, Dhaka", 23.755, 90.385, 35000),
    ("Buriganga Bulk Recyclers", "Old Dhaka, Motijheel, Dhaka", 23.718, 90.410, 28000),
    ("North Metro Collection", "Uttara, Mirpur, Dhaka", 23.855, 90.390, 22000),
    ("Central Circular Materials", "Tejgaon, Farmgate, Banani, Dhaka", 23.780, 90.400, 40000),
    ("Eastern Paper Recovery", "Badda, Dhaka", 23.790, 90.435, 18000),
    ("West Dhaka Recycling Cooperative", "Mohammadpur, Dhanmondi, Dhaka", 23.760, 90.365, 25000),
)
PAPER_SHARES = {
    PaperListing.PaperCategory.OFFICE: .30,
    PaperListing.PaperCategory.BOOKS: .25,
    PaperListing.PaperCategory.NEWS: .16,
    PaperListing.PaperCategory.CARDBOARD: .11,
    PaperListing.PaperCategory.MIXED: .18,
}


def academic_factor(week_start):
    month = week_start.month
    factor = 1.0
    if month in (5, 6, 11, 12):  # final exam and semester-end paper peaks
        factor += .35
    if month in (3, 9):  # midterms
        factor += .14
    if month in (1, 2, 6, 7):  # admission documentation
        factor += .08
    if month in (6, 12):  # semester breaks reduce routine paper generation
        factor -= .22
    return factor


class Command(BaseCommand):
    help = "Seed idempotent synthetic Dhaka institutions, recyclers, waste history, and active listings."

    def add_arguments(self, parser):
        parser.add_argument("--institutions", type=int, default=8)
        parser.add_argument("--recyclers", type=int, default=5)
        parser.add_argument("--weeks", type=int, default=104)
        parser.add_argument("--minimum-records", type=int, default=100)
        parser.add_argument("--seed", type=int, default=42)
        parser.add_argument("--force", action="store_true", help="Fill any missing synthetic weeks even when the database is already populated.")
        parser.add_argument("--allow-non-postgresql", action="store_true",
                            help="Allow seeding SQLite for local development/tests; production pilot seeding expects PostgreSQL.")

    @transaction.atomic
    def handle(self, *args, **options):
        if connection.vendor != "postgresql" and not options["allow_non_postgresql"]:
            raise CommandError(
                "Pilot seeding is restricted to PostgreSQL by default. Configure DATABASE_URL in .env, "
                "or pass --allow-non-postgresql for a disposable local/test database."
            )
        institution_count = options["institutions"]
        recycler_count = options["recyclers"]
        weeks = options["weeks"]
        if not 1 <= institution_count <= len(INSTITUTIONS) or not 0 <= recycler_count <= len(RECYCLERS) or not 4 <= weeks <= 260:
            self.stderr.write(self.style.ERROR("Use 1-12 institutions, 0-6 recyclers, and 4-260 weeks."))
            return
        rng = np.random.default_rng(options["seed"])
        today = timezone.localdate()
        week_end = today - timedelta(days=today.weekday() + 7)
        week_starts = [week_end - timedelta(weeks=offset) for offset in reversed(range(weeks))]

        pilot_institutions = []
        for index, (name, city, latitude, longitude, students) in enumerate(INSTITUTIONS[:institution_count], 1):
            email = f"pilot-institution-{index:02d}@paperloop.test"
            user = User.objects.filter(email__iexact=email).first()
            if user is None:
                user = User.objects.create_user(
                    email=email, password=None, role=UserRole.EDUCATIONAL_INSTITUTION,
                    organization_name=name, verification_status=VerificationStatus.VERIFIED,
                    is_active=True,
                )
            elif user.role != UserRole.EDUCATIONAL_INSTITUTION:
                self.stderr.write(self.style.ERROR(f"Pilot email {email} exists with a different role; skipped."))
                continue
            profile, _ = EducationalInstitution.objects.get_or_create(user=user)
            profile.city, profile.country = city, "Bangladesh"
            profile.institution_type = "Educational institution"
            profile.student_count = students
            profile.latitude, profile.longitude = latitude, longitude
            profile.save(update_fields=("city", "country", "institution_type", "student_count", "latitude", "longitude", "updated_at"))
            pilot_institutions.append((profile, index))

        pilot_recyclers = []
        all_paper_types = list(PAPER_SHARES)
        for index, (name, area, latitude, longitude, capacity) in enumerate(RECYCLERS[:recycler_count], 1):
            email = f"pilot-recycler-{index:02d}@paperloop.test"
            user = User.objects.filter(email__iexact=email).first()
            if user is None:
                user = User.objects.create_user(
                    email=email, password=None, role=UserRole.RECYCLING_PARTNER,
                    organization_name=name, verification_status=VerificationStatus.VERIFIED,
                    is_active=True,
                )
            elif user.role != UserRole.RECYCLING_PARTNER:
                self.stderr.write(self.style.ERROR(f"Pilot email {email} exists with a different role; skipped."))
                continue
            profile, _ = RecyclingProfile.objects.get_or_create(user=user)
            profile.service_area, profile.latitude, profile.longitude = area, latitude, longitude
            profile.accepted_paper_types = all_paper_types
            profile.maximum_capacity = Decimal(capacity)
            profile.capacity_unit = RecyclingProfile.CapacityUnit.KILOGRAM
            profile.capacity_period = RecyclingProfile.CapacityPeriod.MONTH
            profile.collection_available = True
            profile.save(update_fields=("service_area", "latitude", "longitude", "accepted_paper_types",
                                        "maximum_capacity", "capacity_unit", "capacity_period", "collection_available", "updated_at"))
            pilot_recyclers.append(profile)

        seeded_profiles = [row[0] for row in pilot_institutions]
        current_records = WasteRecord.objects.filter(is_synthetic=True, institution__in=seeded_profiles).count()
        created_records = 0
        expected_records = len(pilot_institutions) * weeks * len(PAPER_SHARES)
        should_fill = (options["force"] or current_records < options["minimum_records"]
                       or current_records < expected_records)
        if should_fill:
            existing = set(WasteRecord.objects.filter(
                is_synthetic=True, institution__in=seeded_profiles,
                week_start__in=week_starts,
            ).values_list("institution_id", "week_start", "paper_grade"))
            new_rows = []
            for profile, index in pilot_institutions:
                base_weekly_kg = profile.student_count * .035
                for week_start in week_starts:
                    total = base_weekly_kg * academic_factor(week_start) * float(rng.lognormal(0, .10))
                    for paper_grade, share in PAPER_SHARES.items():
                        key = (profile.pk, week_start, paper_grade)
                        if key in existing:
                            continue
                        weight = max(.1, round(total * share * float(rng.lognormal(0, .08)), 2))
                        new_rows.append(WasteRecord(
                            institution=profile, week_start=week_start, paper_grade=paper_grade,
                            actual_weight_kg=Decimal(str(weight)), is_synthetic=True,
                        ))
            WasteRecord.objects.bulk_create(new_rows, batch_size=1000, ignore_conflicts=True)
            created_records = len(new_rows)

        today_plus = today + timedelta(days=3)
        created_listings = 0
        for profile, index in pilot_institutions:
            if PaperListing.objects.filter(institution=profile, status=PaperListing.Status.AVAILABLE).exists():
                continue
            # One recent week's waste remains a suboptimal solo pickup, making
            # small nearby listings eligible for aggregation.
            latest = list(WasteRecord.objects.filter(institution=profile).order_by("-week_start")[:len(PAPER_SHARES)])
            quantity = sum((row.actual_weight_kg for row in latest), Decimal("0"))
            if quantity <= 0:
                continue
            PaperListing.objects.create(
                institution=profile,
                paper_type=PaperListing.PaperCategory.OFFICE,
                quantity_kg=quantity.quantize(Decimal("0.01")),
                description="Synthetic Dhaka pilot listing; generated for ML workflow validation.",
                pickup_address=profile.address or f"{profile.city}, Dhaka",
                pickup_city=profile.city, pickup_country="Bangladesh",
                available_from=today_plus, available_until=today_plus + timedelta(days=10),
                status=PaperListing.Status.AVAILABLE,
            )
            created_listings += 1

        self.stdout.write(self.style.SUCCESS(
            f"Pilot seed complete on {self.connection_alias}: {len(pilot_institutions)} institutions, "
            f"{len(pilot_recyclers)} recyclers, {created_records} waste rows created, {created_listings} active listings created."
        ))

    @property
    def connection_alias(self):
        from django.db import connection
        return connection.settings_dict["ENGINE"].rsplit(".", 1)[-1]
