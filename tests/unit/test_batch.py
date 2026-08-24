from juval.domain.batch import BatchFile, BatchFileStatus, BatchStatus, aggregate_batch_status


def item(status):
    return BatchFile(0, "file.xlsx", None, 1, status, None)


def test_batch_status_aggregation_is_deterministic():
    assert aggregate_batch_status((item(BatchFileStatus.SUCCESS),)) == BatchStatus.SUCCESS
    assert aggregate_batch_status((item(BatchFileStatus.SUCCESS), item(BatchFileStatus.REJECTED))) == BatchStatus.PARTIAL_SUCCESS
    assert aggregate_batch_status((item(BatchFileStatus.REJECTED),)) == BatchStatus.FAILED

