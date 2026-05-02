"""Unit tests for the background retraining job."""

from unittest.mock import patch, MagicMock

from app.jobs.retrain_job import perform_retraining


def test_background_job_run():
    """U-012: Trigger retrain job manually — completes without raising exceptions."""
    with patch("app.jobs.retrain_job.run_training_pipeline") as mock_train, \
         patch("app.jobs.retrain_job.load_forecast_model") as mock_load:
        mock_train.return_value = None
        mock_load.return_value = True

        # Should complete without raising
        perform_retraining()

        mock_train.assert_called_once()
        mock_load.assert_called_once()


def test_background_job_crash():
    """U-017: Simulate job failure — thread catches error, app remains stable."""
    with patch("app.jobs.retrain_job.run_training_pipeline", side_effect=RuntimeError("Training exploded")), \
         patch("app.jobs.retrain_job.load_forecast_model") as mock_load:

        # Should NOT raise — the function catches exceptions internally
        perform_retraining()

        # load_forecast_model should NOT have been called since training failed
        mock_load.assert_not_called()
