CREATE TABLE IF NOT EXISTS batches (
    batch_id text PRIMARY KEY,
    created_at timestamptz NOT NULL,
    status text NOT NULL CHECK (status IN ('SUCCESS', 'PARTIAL_SUCCESS', 'FAILED'))
);

CREATE TABLE IF NOT EXISTS batch_files (
    batch_id text NOT NULL REFERENCES batches(batch_id) ON DELETE CASCADE,
    ordinal integer NOT NULL,
    filename text NOT NULL,
    content_type text,
    size_bytes bigint NOT NULL,
    status text NOT NULL CHECK (status IN ('SUCCESS', 'PARTIAL_SUCCESS', 'FAILED', 'REJECTED')),
    execution_id text REFERENCES execution_runs(execution_id),
    warnings jsonb NOT NULL DEFAULT '[]'::jsonb,
    errors jsonb NOT NULL DEFAULT '[]'::jsonb,
    PRIMARY KEY (batch_id, ordinal)
);

CREATE INDEX IF NOT EXISTS idx_batch_files_execution ON batch_files (execution_id);
