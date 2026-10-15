"""
MINDS Medication Tracker - create the SQLite database.

Creates the four tables (if they don't exist yet) and,
if there are no staff yet, asks for the first Manager.

Safe to run more than once: it never deletes or overwrites data.

Run from the project folder:
    python -m backend.init_db
"""

from backend.database import get_connection, DB_PATH


TABLES = [

    """
    CREATE TABLE IF NOT EXISTS Trainees (
        trainee_id VARCHAR(10) NOT NULL PRIMARY KEY,
        name VARCHAR(100) NULL,
        unit VARCHAR(100) NULL,
        active BIT NULL
    )
    """,

    """
    CREATE TABLE IF NOT EXISTS Staff (
        staff_id VARCHAR(10) NOT NULL PRIMARY KEY,
        name VARCHAR(100) NULL,
        role VARCHAR(50) NULL,
        unit VARCHAR(100) NULL,
        active BIT NULL,
        microsoft_identity VARCHAR(255) NULL
    )
    """,

    """
    CREATE TABLE IF NOT EXISTS Medications (
        medication_id VARCHAR(10) NOT NULL PRIMARY KEY,
        trainee_id VARCHAR(10) NULL,
        medication_name VARCHAR(100) NULL,
        dosage VARCHAR(100) NULL,
        frequency VARCHAR(50) NULL,
        scheduled_time TIME NULL,
        instructions VARCHAR(255) NULL,
        active BIT NULL
    )
    """,

    """
    CREATE TABLE IF NOT EXISTS MedicationLogs (
        log_id VARCHAR(10) NOT NULL PRIMARY KEY,
        medication_id VARCHAR(10) NULL,
        trainee_id VARCHAR(10) NULL,
        administration_date DATE NULL,
        scheduled_time TIME NULL,
        status VARCHAR(50) NULL,
        given_by VARCHAR(100) NULL,
        witnessed_by VARCHAR(100) NULL,
        actual_time TIME NULL,
        cancellation_reason VARCHAR(255) NULL,
        remarks VARCHAR(255) NULL
    )
    """,
]


def main():

    print(f"Database file: {DB_PATH}")

    connection = get_connection()
    cursor = connection.cursor()

    # 1. Create the tables.
    for sql in TABLES:
        cursor.execute(sql)

    connection.commit()
    print("Tables ready: Trainees, Staff, Medications, MedicationLogs")

    # 2. Add the first Manager if there are no staff yet.
    cursor.execute("SELECT COUNT(*) AS total FROM Staff")
    staff_count = cursor.fetchone().total

    if staff_count > 0:
        print(f"Staff already exist ({staff_count}). No manager added.")

    else:
        print()
        print("No staff yet. Let's add the first Manager (S001).")

        name = ""
        while not name:
            name = input("Manager's full name: ").strip()

        unit = input("Unit [Geylang Serai]: ").strip() or "Geylang Serai"

        cursor.execute("""
            INSERT INTO Staff
                (staff_id, name, role, unit, active, microsoft_identity)
            VALUES
                ('S001', ?, 'Manager', ?, 1, NULL)
        """,
            name,
            unit
        )

        connection.commit()
        print(f"Added S001: {name} (Manager, {unit})")

    cursor.close()
    connection.close()

    print()
    print("Done. Start the app with:")
    print("    uvicorn backend.main:app --host 0.0.0.0 --port 8000")


if __name__ == "__main__":
    main()