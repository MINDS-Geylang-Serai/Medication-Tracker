import os
import struct
import pyodbc
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential


load_dotenv()


def get_connection(server, database):
    credential = DefaultAzureCredential()

    token = credential.get_token(
        "https://database.windows.net/.default"
    )

    token_bytes = token.token.encode("utf-16-le")

    token_struct = struct.pack(
        f"<I{len(token_bytes)}s",
        len(token_bytes),
        token_bytes
    )

    connection_string = (
        "DRIVER={ODBC Driver 18 for SQL Server};"
        f"SERVER={server},1433;"
        f"DATABASE={database};"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
        "Connection Timeout=30;"
    )

    return pyodbc.connect(
        connection_string,
        attrs_before={1256: token_struct}
    )


def main():

    old_server = os.getenv("OLD_DB_SERVER")
    old_database = os.getenv("OLD_DB_NAME")

    new_server = os.getenv("DB_SERVER")
    new_database = os.getenv("DB_NAME")

    print("Connecting to old database...")
    old_connection = get_connection(
        old_server,
        old_database
    )

    print("Connecting to new database...")
    new_connection = get_connection(
        new_server,
        new_database
    )

    old_cursor = old_connection.cursor()
    new_cursor = new_connection.cursor()

    print("Connected to both databases.")

    # --------------------------------------------------
    # 1. Create tables in the new database
    # --------------------------------------------------

    print("Creating tables in new database...")

    new_cursor.execute("""
        IF OBJECT_ID('Trainees', 'U') IS NULL
        CREATE TABLE Trainees (
            trainee_id VARCHAR(10) PRIMARY KEY,
            name VARCHAR(100),
            unit VARCHAR(100),
            active BIT
        )
    """)

    new_cursor.execute("""
        IF OBJECT_ID('Staff', 'U') IS NULL
        CREATE TABLE Staff (
            staff_id VARCHAR(10) PRIMARY KEY,
            name VARCHAR(100),
            role VARCHAR(50),
            unit VARCHAR(100),
            active BIT
        )
    """)

    new_cursor.execute("""
        IF OBJECT_ID('Medications', 'U') IS NULL
        CREATE TABLE Medications (
            medication_id VARCHAR(10) PRIMARY KEY,
            trainee_id VARCHAR(10),
            medication_name VARCHAR(100),
            dosage VARCHAR(100),
            frequency VARCHAR(50),
            scheduled_time TIME,
            instructions VARCHAR(255),
            active BIT
        )
    """)

    new_cursor.execute("""
        IF OBJECT_ID('MedicationLogs', 'U') IS NULL
        CREATE TABLE MedicationLogs (
            log_id VARCHAR(10) PRIMARY KEY,
            medication_id VARCHAR(10),
            trainee_id VARCHAR(10),
            administration_date DATE,
            scheduled_time TIME,
            status VARCHAR(50),
            given_by VARCHAR(100),
            witnessed_by VARCHAR(100),
            actual_time TIME,
            cancellation_reason VARCHAR(255),
            remarks VARCHAR(255)
        )
    """)

    new_connection.commit()

    print("Tables created.")

    # --------------------------------------------------
    # 2. Copy Trainees
    # --------------------------------------------------

    print("Copying Trainees...")

    old_cursor.execute("""
        SELECT
            trainee_id,
            name,
            unit,
            active
        FROM Trainees
    """)

    trainees = old_cursor.fetchall()

    for row in trainees:
        new_cursor.execute("""
            INSERT INTO Trainees (
                trainee_id,
                name,
                unit,
                active
            )
            VALUES (?, ?, ?, ?)
        """,
            row.trainee_id,
            row.name,
            row.unit,
            row.active
        )

    print(f"Copied {len(trainees)} Trainees.")

    # --------------------------------------------------
    # 3. Copy Staff
    # --------------------------------------------------

    print("Copying Staff...")

    old_cursor.execute("""
        SELECT
            staff_id,
            name,
            role,
            unit,
            active
        FROM Staff
    """)

    staff = old_cursor.fetchall()

    for row in staff:
        new_cursor.execute("""
            INSERT INTO Staff (
                staff_id,
                name,
                role,
                unit,
                active
            )
            VALUES (?, ?, ?, ?, ?)
        """,
            row.staff_id,
            row.name,
            row.role,
            row.unit,
            row.active
        )

    print(f"Copied {len(staff)} Staff records.")

    # --------------------------------------------------
    # 4. Copy Medications
    # --------------------------------------------------

    print("Copying Medications...")

    old_cursor.execute("""
        SELECT
            medication_id,
            trainee_id,
            medication_name,
            dosage,
            frequency,
            scheduled_time,
            instructions,
            active
        FROM Medications
    """)

    medications = old_cursor.fetchall()

    for row in medications:
        new_cursor.execute("""
            INSERT INTO Medications (
                medication_id,
                trainee_id,
                medication_name,
                dosage,
                frequency,
                scheduled_time,
                instructions,
                active
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            row.medication_id,
            row.trainee_id,
            row.medication_name,
            row.dosage,
            row.frequency,
            row.scheduled_time,
            row.instructions,
            row.active
        )

    print(f"Copied {len(medications)} Medications.")

    # --------------------------------------------------
    # 5. Copy MedicationLogs
    # --------------------------------------------------

    print("Copying MedicationLogs...")

    old_cursor.execute("""
        SELECT
            log_id,
            medication_id,
            trainee_id,
            administration_date,
            scheduled_time,
            status,
            given_by,
            witnessed_by,
            actual_time,
            cancellation_reason,
            remarks
        FROM MedicationLogs
    """)

    logs = old_cursor.fetchall()

    for row in logs:
        new_cursor.execute("""
            INSERT INTO MedicationLogs (
                log_id,
                medication_id,
                trainee_id,
                administration_date,
                scheduled_time,
                status,
                given_by,
                witnessed_by,
                actual_time,
                cancellation_reason,
                remarks
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            row.log_id,
            row.medication_id,
            row.trainee_id,
            row.administration_date,
            row.scheduled_time,
            row.status,
            row.given_by,
            row.witnessed_by,
            row.actual_time,
            row.cancellation_reason,
            row.remarks
        )

    print(f"Copied {len(logs)} MedicationLogs.")

    # --------------------------------------------------
    # 6. Commit everything
    # --------------------------------------------------

    new_connection.commit()

    print()
    print("Migration completed successfully.")
    print()
    print("Old database was NOT modified.")

    old_connection.close()
    new_connection.close()


if __name__ == "__main__":
    main()