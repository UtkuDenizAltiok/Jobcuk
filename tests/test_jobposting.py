import json
from datetime import UTC, datetime

from jobcu.jobposting import find_job_posting
from jobcu.sources.adzuna import AdzunaSource


def page(posting: dict, wrap_in_graph=False) -> str:
    data = {"@context": "https://schema.org", "@graph": [{"@type": "WebPage"}, posting]} \
        if wrap_in_graph else posting
    return f'<html><script type="application/ld+json">{json.dumps(data)}</script></html>'


POSTING = {
    "@type": "JobPosting",
    "title": "Power Electronics Engineer",
    "description": "<p>You design <b>inverters</b>.</p><ul><li>PCB layout</li></ul>" * 10,
    "datePosted": "2026-09-16T08:30:00+02:00",
    "employmentType": ["FULL_TIME", "INTERN"],
    "hiringOrganization": {"@type": "Organization", "name": "Acme GmbH"},
    "jobLocation": [{"@type": "Place", "address": {"addressLocality": "München"}}],
    "jobLocationType": "TELECOMMUTE",
}


def test_job_posting_data_is_read_even_inside_a_graph():
    posting = find_job_posting(page(POSTING, wrap_in_graph=True))
    assert posting.title == "Power Electronics Engineer"
    assert "• PCB layout" in posting.description and "<b>" not in posting.description
    assert posting.date_posted == datetime(2026, 9, 16, 6, 30, tzinfo=UTC)
    assert posting.company == "Acme GmbH" and posting.location_text == "München"
    assert posting.job_types == ["full_time_permanent", "fixed_term",
                                 "internship_or_working_student"]
    assert posting.remote


def test_pages_without_job_data_give_nothing():
    assert find_job_posting("<html><script type='application/ld+json'>{bad json</script>") is None
    assert find_job_posting(page({"@type": "Organization"})) is None


def test_adzuna_never_reads_its_own_job_pages():
    # Its firewall and robots.txt refuse Jobcu (DECISIONS.md 2026-09-24): the full ad comes from
    # the same job on another site, or from the person's AI reading it online.
    from jobcu.sources.base import JobSource

    assert AdzunaSource.load_details is JobSource.load_details
