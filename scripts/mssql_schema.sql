IF DB_ID(N'NetDiagAgent') IS NULL
BEGIN
    CREATE DATABASE NetDiagAgent;
END;
GO

USE NetDiagAgent;
GO

IF OBJECT_ID(N'dbo.netdiag_users', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.netdiag_users (
        user_id UNIQUEIDENTIFIER NOT NULL CONSTRAINT PK_netdiag_users PRIMARY KEY DEFAULT NEWID(),
        username NVARCHAR(32) NOT NULL,
        password_hash VARBINARY(32) NOT NULL,
        password_salt VARBINARY(16) NOT NULL,
        password_scheme NVARCHAR(64) NOT NULL,
        device_hash CHAR(64) NOT NULL,
        created_at_utc DATETIME2(3) NOT NULL CONSTRAINT DF_netdiag_users_created DEFAULT SYSUTCDATETIME(),
        last_login_at_utc DATETIME2(3) NULL,
        CONSTRAINT UQ_netdiag_users_username UNIQUE (username),
        CONSTRAINT UQ_netdiag_users_device UNIQUE (device_hash)
    );
END;
GO

IF OBJECT_ID(N'dbo.netdiag_diagnosis_logs', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.netdiag_diagnosis_logs (
        log_id BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_netdiag_diagnosis_logs PRIMARY KEY,
        user_id UNIQUEIDENTIFIER NOT NULL,
        username_snapshot NVARCHAR(32) NOT NULL,
        device_hash CHAR(64) NOT NULL,
        created_at_utc DATETIME2(3) NOT NULL CONSTRAINT DF_netdiag_logs_created DEFAULT SYSUTCDATETIME(),
        status NVARCHAR(16) NOT NULL,
        dataset_source NVARCHAR(260) NULL,
        dataset_fingerprint CHAR(64) NULL,
        dataset_rows INT NULL,
        dataset_columns INT NULL,
        model NVARCHAR(128) NULL,
        task NVARCHAR(2000) NOT NULL,
        tool_records_json NVARCHAR(MAX) NULL,
        evidence_json NVARCHAR(MAX) NULL,
        report NVARCHAR(MAX) NULL,
        error_message NVARCHAR(1000) NULL,
        CONSTRAINT FK_netdiag_logs_user FOREIGN KEY (user_id) REFERENCES dbo.netdiag_users(user_id),
        CONSTRAINT CK_netdiag_logs_status CHECK (status IN (N'success', N'error'))
    );
    CREATE INDEX IX_netdiag_logs_user_time
        ON dbo.netdiag_diagnosis_logs(user_id, created_at_utc DESC);
END;
GO

SELECT username, password_scheme, device_hash, created_at_utc, last_login_at_utc
FROM dbo.netdiag_users
ORDER BY created_at_utc DESC;

SELECT TOP 50 log_id, username_snapshot, created_at_utc, status, dataset_source, model, task
FROM dbo.netdiag_diagnosis_logs
ORDER BY created_at_utc DESC, log_id DESC;
