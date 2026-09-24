"""Job sources: one isolated module per source. A failing source never breaks a search."""

from jobcu.sources.adzuna import AdzunaSource
from jobcu.sources.arbeitnow import ArbeitnowSource
from jobcu.sources.ashby import AshbySource
from jobcu.sources.base import JobSource
from jobcu.sources.bundesagentur import BundesagenturSource
from jobcu.sources.careers import CareerSystemSource
from jobcu.sources.euraxess import EuraxessSource
from jobcu.sources.greenhouse import GreenhouseSource
from jobcu.sources.jobsacuk import JobsAcUkSource
from jobcu.sources.jobsireland import JobsIrelandSource
from jobcu.sources.jobtech import JobTechSource
from jobcu.sources.leforem import LeForemSource
from jobcu.sources.lever import LeverSource
from jobcu.sources.nhsjobs import NhsJobsSource
from jobcu.sources.prospective import ProspectiveSource
from jobcu.sources.recruitee import RecruiteeSource
from jobcu.sources.reed import ReedSource
from jobcu.sources.servicebund import ServiceBundSource
from jobcu.sources.successfactors import SuccessFactorsSource
from jobcu.sources.teachingvacancies import TeachingVacanciesSource
from jobcu.sources.teamtailor import TeamtailorSource
from jobcu.sources.werkenvoornederland import WerkenVoorNederlandSource
from jobcu.sources.workable import WorkableSource
from jobcu.sources.workday import WorkdaySource


def career_sources() -> list[CareerSystemSource]:
    """Company career systems, read for the employers in the employer directory."""
    return [AshbySource(), GreenhouseSource(), LeverSource(), ProspectiveSource(),
            RecruiteeSource(), SuccessFactorsSource(), TeamtailorSource(), WorkableSource(),
            WorkdaySource()]


def all_sources() -> list[JobSource]:
    """Fresh source objects for one search, in the order they're shown."""
    return [AdzunaSource(), ArbeitnowSource(), JobTechSource(), BundesagenturSource(),
            ServiceBundSource(), EuraxessSource(), JobsAcUkSource(), JobsIrelandSource(),
            ReedSource(), TeachingVacanciesSource(), NhsJobsSource(), LeForemSource(),
            WerkenVoorNederlandSource(), *career_sources()]
