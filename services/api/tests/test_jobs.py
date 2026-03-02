from api.jobs import JobUpdate


def test_job_update_defaults() -> None:
    update = JobUpdate()
    assert update.status is None
    assert update.progress is None
    assert update.progress_message is None
    assert update.result is None


def test_job_update_with_values() -> None:
    update = JobUpdate(
        status="running",
        progress=50,
        progress_message="Extracting...",
    )
    assert update.status == "running"
    assert update.progress == 50
    assert update.progress_message == "Extracting..."
    assert update.result is None
