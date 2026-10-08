from fastapi import FastAPI, HTTPException, Request

from pydantic import BaseModel

from fastapi.middleware.cors import CORSMiddleware

from fastapi.staticfiles import StaticFiles

from fastapi.responses import FileResponse

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from backend.database import get_connection

import base64

import json

app = FastAPI()


#switch for current test login vs eventual Microsoft Authentication
import os


DEV_LOGIN = os.getenv(
    "DEV_LOGIN",
    "true"
).lower() == "true"


# Asks - who is making this request?
def get_current_staff(
    request: Request
):
    """
    Determines which staff member is making the request.

    Development:
        Uses the X-Dev-Staff-ID header.

    Production:
        Uses the Microsoft Entra identity
        provided by Azure App Service.
    """

    if DEV_LOGIN:

        staff_id = request.headers.get(
            "X-Dev-Staff-ID"
        )

        if not staff_id:

            raise HTTPException(
                status_code=401,
                detail="Not logged in."
            )

        return staff_id


    # Production:
    # Azure App Service Authentication provides
    # the authenticated Microsoft identity here.

    client_principal = request.headers.get(
        "X-MS-CLIENT-PRINCIPAL"
    )

    if not client_principal:

        raise HTTPException(
            status_code=401,
            detail="Microsoft authentication is required."
        )


    try:

        decoded = base64.b64decode(
            client_principal
        )

        principal = json.loads(
            decoded
        )

    except Exception as error:

        print(
            "ERROR decoding Microsoft identity:",
            error
        )

        raise HTTPException(
            status_code=401,
            detail="Unable to read Microsoft identity."
        )


    identity = None


    for claim in principal.get(
        "claims",
        []
    ):

        claim_type = claim.get(
            "typ",
            ""
        )

        if claim_type in [
            "oid",
            "http://schemas.microsoft.com/identity/claims/objectidentifier"
        ]:

            identity = claim.get(
                "val"
            )

            break


    if not identity:

        raise HTTPException(
            status_code=401,
            detail="Microsoft identity could not be identified."
        )


    connection = None
    cursor = None

    try:

        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                staff_id
            FROM Staff
            WHERE microsoft_identity = ?
              AND active = 1
        """,
            identity
        )

        row = cursor.fetchone()

        if not row:

            raise HTTPException(
                status_code=403,
                detail="Your Microsoft account is not authorised to use this system."
            )

        return row.staff_id

    except HTTPException:
        raise

    except Exception as error:

        print(
            "ERROR mapping Microsoft identity:",
            error
        )

        raise HTTPException(
            status_code=503,
            detail="Medication system is temporarily unavailable."
        )

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()

# =========================================================
# MODELS
# =========================================================

class LoginRequest(BaseModel):
    staff_id: str


class StaffCreate(BaseModel):
    name: str
    role: str
    unit: str | None = None
    microsoft_identity: str | None = None


class StaffUpdate(BaseModel):
    name: str
    role: str
    unit: str | None = None
    active: bool
    microsoft_identity: str | None = None


class TraineeCreate(BaseModel):
    name: str
    unit: str


class TraineeUpdate(BaseModel):
    name: str
    unit: str
    active: bool


class MedicationCreate(BaseModel):
    trainee_id: str
    medication_name: str
    dosage: str
    frequency: str
    scheduled_time: str
    instructions: str | None = None


class MedicationUpdate(BaseModel):
    medication_name: str
    dosage: str
    frequency: str
    scheduled_time: str
    instructions: str | None = None
    active: bool


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# FRONTEND
# =========================================================

app.mount(
    "/frontend",
    StaticFiles(directory="frontend"),
    name="frontend"
)


@app.get("/")
def home():
    return FileResponse("frontend/index.html")


@app.get("/manager.html")
def manager_page():
    return FileResponse("frontend/manager.html")


@app.get("/history.html")
def history_page():
    return FileResponse("frontend/history.html")


# =========================================================
# LOGIN
# =========================================================

@app.post("/login")
def login(
    request: Request
):

    connection = None
    cursor = None

    try:

        staff_id = get_current_staff(
            request
        )

        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                staff_id,
                name,
                role,
                unit
            FROM Staff
            WHERE staff_id = ?
              AND active = 1
        """, staff_id)

        row = cursor.fetchone()

        if not row:

            raise HTTPException(
                status_code=401,
                detail="Invalid staff account"
            )

        return {
            "staff_id": row.staff_id,
            "name": row.name,
            "role": row.role,
            "unit": row.unit
        }

    except HTTPException:
        raise

    except Exception as error:

        print(
            "ERROR during login:",
            error
        )

        raise HTTPException(
            status_code=503,
            detail="Medication system is temporarily unavailable."
        )

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()

# =========================================================
# VALIDATE AUTHORITY
# =========================================================

@app.get("/me")
def get_me(
    request: Request
):

    staff_id = get_current_staff(
        request
    )

    connection = None
    cursor = None

    try:

        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                staff_id,
                name,
                role,
                unit
            FROM Staff
            WHERE staff_id = ?
              AND active = 1
        """, staff_id)

        row = cursor.fetchone()

        if not row:

            raise HTTPException(
                status_code=401,
                detail="Invalid staff account."
            )

        return {
            "staff_id": row.staff_id,
            "name": row.name,
            "role": row.role,
            "unit": row.unit
        }

    except HTTPException:
        raise

    except Exception as error:

        print(
            "ERROR loading current staff:",
            error
        )

        raise HTTPException(
            status_code=503,
            detail="Medication system is temporarily unavailable."
        )

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()



# =========================================================
# GET STAFF
# Existing endpoint used by the Training Officer app
# Only returns active staff.
# =========================================================

@app.get("/staff")
def get_staff():

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                staff_id,
                name,
                role,
                unit
            FROM Staff
            WHERE active = 1
            ORDER BY name
        """)

        rows = cursor.fetchall()

        staff = []

        for row in rows:
            staff.append({
                "staff_id": row.staff_id,
                "name": row.name,
                "role": row.role,
                "unit": row.unit
            })

        return staff

    except Exception as error:
        print("ERROR loading staff:", error)

        raise HTTPException(
            status_code=503,
            detail="Medication system is temporarily unavailable."
        )

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()


# =========================================================
# MANAGER - GET ALL STAFF
# Includes inactive staff.
# =========================================================

@app.get("/manager/staff")
def get_manager_staff(
    request: Request
):

    connection = None
    cursor = None

    try:

        staff_id = get_current_staff(
            request
        )

        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                staff_id,
                name,
                role,
                unit,
                active,
                microsoft_identity
            FROM Staff
            WHERE staff_id = ?
              AND active = 1
        """, staff_id)

        current_staff = cursor.fetchone()

        if not current_staff:

            raise HTTPException(
                status_code=401,
                detail="Invalid staff account"
            )

        if current_staff.role != "Manager":

            raise HTTPException(
                status_code=403,
                detail="Manager access required."
            )

        cursor.execute("""
            SELECT
                staff_id,
                name,
                role,
                unit,
                active,
                microsoft_identity
            FROM Staff
            ORDER BY name
        """)

        rows = cursor.fetchall()

        staff = []

        for row in rows:

            staff.append({
                "staff_id": row.staff_id,
                "name": row.name,
                "role": row.role,
                "unit": row.unit,
                "active": bool(row.active),
                "microsoft_identity":
                    row.microsoft_identity
            })

        return staff

    except HTTPException:
        raise

    except Exception as error:

        print(
            "ERROR loading manager staff:",
            error
        )

        raise HTTPException(
            status_code=503,
            detail="Medication system is temporarily unavailable."
        )

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# =========================================================
# MANAGER - CREATE STAFF
# =========================================================

@app.post("/manager/staff")
def create_staff(staff: StaffCreate):

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT staff_id
            FROM Staff
            WHERE staff_id LIKE 'S%'
        """)

        rows = cursor.fetchall()

        highest_number = 0

        for row in rows:
            try:
                number = int(row.staff_id[1:])

                if number > highest_number:
                    highest_number = number

            except (ValueError, TypeError):
                continue

        new_staff_id = f"S{highest_number + 1:03d}"

        cursor.execute("""
            INSERT INTO Staff
                (
                    staff_id,
                    name,
                    role,
                    unit,
                    active,
                    microsoft_identity
                )
            VALUES
                (?, ?, ?, ?, 1, ?)
        """,
            new_staff_id,
            staff.name,
            staff.role,
            staff.unit,
            staff.microsoft_identity
        )

        connection.commit()

        return {
            "message": "Staff created successfully.",
            "staff_id": new_staff_id
        }

    except HTTPException:
        raise

    except Exception as error:
        print("ERROR creating staff:", error)

        if connection:
            try:
                connection.rollback()
            except Exception:
                pass

        raise HTTPException(
            status_code=503,
            detail="Unable to create staff record."
        )

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()

# =========================================================
# MANAGER - UPDATE STAFF
# =========================================================

@app.put("/manager/staff/{staff_id}")
def update_staff(
    staff_id: str,
    staff: StaffUpdate
):

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT staff_id
            FROM Staff
            WHERE staff_id = ?
        """, staff_id)

        row = cursor.fetchone()

        if not row:
            raise HTTPException(
                status_code=404,
                detail="Staff member not found."
            )

        cursor.execute("""
            UPDATE Staff
            SET
                name = ?,
                role = ?,
                unit = ?,
                active = ?,
                microsoft_identity = ?
            WHERE staff_id = ?
        """,
            staff.name,
            staff.role,
            staff.unit,
            1 if staff.active else 0,
            staff.microsoft_identity,
            staff_id
        )

        connection.commit()

        return {
            "message": "Staff updated successfully.",
            "staff_id": staff_id
        }

    except HTTPException:
        raise

    except Exception as error:
        print("ERROR updating staff:", error)

        if connection:
            try:
                connection.rollback()
            except Exception:
                pass

        raise HTTPException(
            status_code=503,
            detail="Unable to update staff record."
        )

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()

# =========================================================
# MANAGER - GET ALL TRAINEES
# Includes inactive trainees.
# =========================================================

@app.get("/manager/trainees")
def get_manager_trainees():

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                trainee_id,
                name,
                unit,
                active
            FROM Trainees
            ORDER BY name
        """)

        rows = cursor.fetchall()

        trainees = []

        for row in rows:
            trainees.append({
                "trainee_id": row.trainee_id,
                "name": row.name,
                "unit": row.unit,
                "active": bool(row.active)
            })

        return trainees

    except Exception as error:
        print("ERROR loading manager trainees:", error)

        raise HTTPException(
            status_code=503,
            detail="Medication system is temporarily unavailable."
        )

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()


# =========================================================
# MANAGER - CREATE TRAINEE
# =========================================================

@app.post("/manager/trainees")
def create_trainee(trainee: TraineeCreate):

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT trainee_id
            FROM Trainees
            WHERE trainee_id LIKE 'T%'
        """)

        rows = cursor.fetchall()

        highest_number = 0

        for row in rows:
            try:
                number = int(row.trainee_id[1:])

                if number > highest_number:
                    highest_number = number

            except (ValueError, TypeError):
                continue

        new_trainee_id = f"T{highest_number + 1:03d}"

        cursor.execute("""
            INSERT INTO Trainees
                (trainee_id, name, unit, active)
            VALUES
                (?, ?, ?, 1)
        """,
            new_trainee_id,
            trainee.name,
            trainee.unit
        )

        connection.commit()

        return {
            "message": "Trainee created successfully.",
            "trainee_id": new_trainee_id
        }

    except HTTPException:
        raise

    except Exception as error:
        print("ERROR creating trainee:", error)

        if connection:
            try:
                connection.rollback()
            except Exception:
                pass

        raise HTTPException(
            status_code=503,
            detail="Unable to create trainee record."
        )

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()


# =========================================================
# MANAGER - UPDATE TRAINEE
# =========================================================

@app.put("/manager/trainees/{trainee_id}")
def update_trainee(
    trainee_id: str,
    trainee: TraineeUpdate
):

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT trainee_id
            FROM Trainees
            WHERE trainee_id = ?
        """, trainee_id)

        row = cursor.fetchone()

        if not row:
            raise HTTPException(
                status_code=404,
                detail="Trainee not found."
            )

        cursor.execute("""
            UPDATE Trainees
            SET
                name = ?,
                unit = ?,
                active = ?
            WHERE trainee_id = ?
        """,
            trainee.name,
            trainee.unit,
            1 if trainee.active else 0,
            trainee_id
        )

        connection.commit()

        return {
            "message": "Trainee updated successfully.",
            "trainee_id": trainee_id
        }

    except HTTPException:
        raise

    except Exception as error:
        print("ERROR updating trainee:", error)

        if connection:
            try:
                connection.rollback()
            except Exception:
                pass

        raise HTTPException(
            status_code=503,
            detail="Unable to update trainee record."
        )

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()


# =========================================================
# GET TRAINEES
# Existing endpoint used by history.
# Only active trainees.
# =========================================================

@app.get("/trainees")
def get_trainees():

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                trainee_id,
                name
            FROM Trainees
            WHERE active = 1
            ORDER BY name
        """)

        rows = cursor.fetchall()

        trainees = []

        for row in rows:
            trainees.append({
                "trainee_id": row.trainee_id,
                "name": row.name
            })

        return trainees

    except Exception as error:
        print("ERROR loading trainees:", error)

        raise HTTPException(
            status_code=503,
            detail="Medication system is temporarily unavailable."
        )

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()


# =========================================================
# MANAGER - GET ALL MEDICATIONS
# Includes inactive medications.
# =========================================================

@app.get("/manager/medications")
def get_manager_medications():

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                m.medication_id,
                m.trainee_id,
                t.name AS trainee_name,
                m.medication_name,
                m.dosage,
                m.frequency,
                m.scheduled_time,
                m.instructions,
                m.active
            FROM Medications m
            JOIN Trainees t
                ON m.trainee_id = t.trainee_id
            ORDER BY
                t.name,
                m.scheduled_time,
                m.medication_name
        """)

        rows = cursor.fetchall()

        medications = []

        for row in rows:
            medications.append({
                "medication_id": row.medication_id,
                "trainee_id": row.trainee_id,
                "trainee_name": row.trainee_name,
                "medication_name": row.medication_name,
                "dosage": row.dosage,
                "frequency": row.frequency,
                "scheduled_time": str(row.scheduled_time),
                "instructions": row.instructions,
                "active": bool(row.active)
            })

        return medications

    except Exception as error:
        print("ERROR loading manager medications:", error)

        raise HTTPException(
            status_code=503,
            detail="Medication system is temporarily unavailable."
        )

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()


# =========================================================
# MANAGER - CREATE MEDICATION
# =========================================================

@app.post("/manager/medications")
def create_medication(
    medication: MedicationCreate
):

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT trainee_id
            FROM Trainees
            WHERE trainee_id = ?
        """, medication.trainee_id)

        trainee = cursor.fetchone()

        if not trainee:
            raise HTTPException(
                status_code=404,
                detail="Trainee not found."
            )

        cursor.execute("""
            SELECT trainee_id, active
            FROM Trainees
            WHERE trainee_id = ?
        """, medication.trainee_id)

        trainee_status = cursor.fetchone()

        if not trainee_status or not trainee_status.active:
            raise HTTPException(
                status_code=400,
                detail="Cannot create medication for an inactive trainee."
            )

        cursor.execute("""
            SELECT medication_id
            FROM Medications
            WHERE medication_id LIKE 'M%'
        """)

        rows = cursor.fetchall()

        highest_number = 0

        for row in rows:
            try:
                number = int(row.medication_id[1:])

                if number > highest_number:
                    highest_number = number

            except (ValueError, TypeError):
                continue

        new_medication_id = f"M{highest_number + 1:03d}"

        cursor.execute("""
            INSERT INTO Medications
                (
                    medication_id,
                    trainee_id,
                    medication_name,
                    dosage,
                    frequency,
                    scheduled_time,
                    instructions,
                    active
                )
            VALUES
                (?, ?, ?, ?, ?, ?, ?, 1)
        """,
            new_medication_id,
            medication.trainee_id,
            medication.medication_name,
            medication.dosage,
            medication.frequency,
            medication.scheduled_time,
            medication.instructions
        )

        connection.commit()

        return {
            "message": "Medication created successfully.",
            "medication_id": new_medication_id
        }

    except HTTPException:
        raise

    except Exception as error:
        print("ERROR creating medication:", error)

        if connection:
            try:
                connection.rollback()
            except Exception:
                pass

        raise HTTPException(
            status_code=503,
            detail="Unable to create medication record."
        )

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()


# =========================================================
# MANAGER - UPDATE MEDICATION
# =========================================================

@app.put("/manager/medications/{medication_id}")
def update_medication(
    medication_id: str,
    medication: MedicationUpdate
):

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT medication_id
            FROM Medications
            WHERE medication_id = ?
        """, medication_id)

        row = cursor.fetchone()

        if not row:
            raise HTTPException(
                status_code=404,
                detail="Medication not found."
            )

        cursor.execute("""
            UPDATE Medications
            SET
                medication_name = ?,
                dosage = ?,
                frequency = ?,
                scheduled_time = ?,
                instructions = ?,
                active = ?
            WHERE medication_id = ?
        """,
            medication.medication_name,
            medication.dosage,
            medication.frequency,
            medication.scheduled_time,
            medication.instructions,
            1 if medication.active else 0,
            medication_id
        )

        connection.commit()

        return {
            "message": "Medication updated successfully.",
            "medication_id": medication_id
        }

    except HTTPException:
        raise

    except Exception as error:
        print("ERROR updating medication:", error)

        if connection:
            try:
                connection.rollback()
            except Exception:
                pass

        raise HTTPException(
            status_code=503,
            detail="Unable to update medication record."
        )

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()


# =========================================================
# RECURRING MEDICATION SCHEDULING
# =========================================================

def medication_occurs_today(
    frequency: str,
    today: date
):
    """
    Determines whether a medication should occur on a given date.

    Supported for now:
        Daily
        Weekdays
    """

    if frequency == "Daily":
        return today.weekday() < 5

    if frequency == "Weekdays":
        return today.weekday() < 5

    return False


def ensure_today_medication_logs(
    connection,
    cursor
):
    """
    Creates today's MedicationLog records for active
    medications that are scheduled to occur today.

    Existing logs are never duplicated.
    """

    singapore_now = datetime.now(
        ZoneInfo("Asia/Singapore")
    )
    
    print(
        "SINGAPORE NOW:",
        singapore_now
    )

    today = singapore_now.date()

    # -----------------------------------------------------
    # Mark today's unfinished medications as
    # Not Administered after the 7:00 PM cutoff.
    # -----------------------------------------------------

    cutoff_time = time(19, 0)

    if singapore_now.time() >= cutoff_time:

        print(
            "CUTOFF REACHED - marking today's Pending logs as Not Administered"
        )

        cursor.execute("""
            UPDATE MedicationLogs
            SET status = 'Not Administered'
            WHERE administration_date = ?
              AND status = 'Pending'
        """,
            today
        )
        
        print(
            "ROWS UPDATED:",
            cursor.rowcount
        )

    # -----------------------------------------------------
    # Find active medication schedules
    # and only active trainees.
    # -----------------------------------------------------

    cursor.execute("""
        SELECT
            m.medication_id,
            m.trainee_id,
            m.frequency,
            m.scheduled_time
        FROM Medications m
        JOIN Trainees t
            ON m.trainee_id = t.trainee_id
        WHERE m.active = 1
          AND t.active = 1
    """)

    medications = cursor.fetchall()

    for medication in medications:

        if not medication_occurs_today(
            medication.frequency,
            today
        ):
            continue

        # -------------------------------------------------
        # Check whether today's occurrence already exists.
        # -------------------------------------------------

        cursor.execute("""
            SELECT log_id
            FROM MedicationLogs
            WHERE medication_id = ?
              AND administration_date = ?
              AND scheduled_time = ?
        """,
            medication.medication_id,
            today,
            medication.scheduled_time
        )

        existing_log = cursor.fetchone()

        if existing_log:
            continue

        # -------------------------------------------------
        # Generate a new log ID.
        # -------------------------------------------------

        cursor.execute("""
            SELECT log_id
            FROM MedicationLogs
            WHERE log_id LIKE 'L%'
        """)

        existing_ids = cursor.fetchall()

        highest_number = 0

        for row in existing_ids:

            try:
                number = int(row.log_id[1:])

                if number > highest_number:
                    highest_number = number

            except (ValueError, TypeError):
                continue

        new_log_id = f"L{highest_number + 1:03d}"

        # -------------------------------------------------
        # Create today's pending medication occurrence.
        # -------------------------------------------------

        cursor.execute("""
            INSERT INTO MedicationLogs
                (
                    log_id,
                    medication_id,
                    trainee_id,
                    administration_date,
                    scheduled_time,
                    status
                )
            SELECT
                ?,
                m.medication_id,
                m.trainee_id,
                ?,
                m.scheduled_time,
                'Pending'
            FROM Medications m
            WHERE m.medication_id = ?
        """,
            new_log_id,
            today,
            medication.medication_id
        )


# =========================================================
# GET MEDICATION LOGS
# This now generates today's recurring records first.
# =========================================================

@app.get("/medications")
def get_medications():

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        singapore_now = datetime.now(
            ZoneInfo("Asia/Singapore")
        )

        today = singapore_now.date()

        # -------------------------------------------------
        # Generate today's medication occurrences.
        # -------------------------------------------------

        ensure_today_medication_logs(
            connection,
            cursor
        )

        connection.commit()

        # -------------------------------------------------
        # Return today's medication logs only.
        # -------------------------------------------------

        cursor.execute("""
            SELECT
                ml.log_id,
                ml.medication_id,
                ml.trainee_id,
                t.name AS trainee,
                m.medication_name,
                m.dosage,
                m.instructions,
                ml.scheduled_time,
                ml.status,
                ml.given_by,
                given_staff.name AS given_by_name,
                ml.witnessed_by,
                witnessed_staff.name AS witnessed_by_name,
                ml.actual_time,
                ml.cancellation_reason,
                ml.remarks
            FROM MedicationLogs ml

            JOIN Trainees t
                ON ml.trainee_id = t.trainee_id

            JOIN Medications m
                ON ml.medication_id = m.medication_id

            LEFT JOIN Staff given_staff
                ON ml.given_by = given_staff.staff_id

            LEFT JOIN Staff witnessed_staff
                ON ml.witnessed_by = witnessed_staff.staff_id

            WHERE ml.administration_date = ?

            ORDER BY
                ml.scheduled_time ASC
        """,
            today
        )

        rows = cursor.fetchall()

        medications = []

        for row in rows:

            medications.append({
                "log_id": row.log_id,
                "medication_id": row.medication_id,
                "trainee_id": row.trainee_id,
                "trainee": row.trainee,
                "medication": row.medication_name,
                "dosage": row.dosage,
                "instructions": row.instructions,
                "scheduled_time": str(row.scheduled_time),
                "status": row.status,

                "given_by": row.given_by,
                "given_by_name": row.given_by_name,

                "witnessed_by": row.witnessed_by,
                "witnessed_by_name": row.witnessed_by_name,

                "actual_time": (
                    row.actual_time.isoformat()
                    if row.actual_time
                    else None
                ),

                "cancellation_reason": row.cancellation_reason,
                "remarks": row.remarks
            })

        return medications

    except Exception as error:
        print("ERROR loading medications:", error)

        if connection:
            try:
                connection.rollback()
            except Exception:
                pass

        raise HTTPException(
            status_code=503,
            detail="Medication system is temporarily unavailable."
        )

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()


# =========================================================
# ADMINISTER MEDICATION
# =========================================================

@app.put("/medications/{log_id}/administer")
def administer_medication(
    log_id: str,
    witnessed_by: str,
    remarks: str = ""
):

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT status
            FROM MedicationLogs
            WHERE log_id = ?
        """, log_id)

        row = cursor.fetchone()

        if row is None:
            return {
                "error": "Medication log not found."
            }

        if row.status != "Pending":
            return {
                "error": "This medication has already been completed."
            }

        # Prototype current Training Officer
        given_by = "S002"

        cursor.execute("""
            UPDATE MedicationLogs
            SET
                status = 'Administered',
                given_by = ?,
                witnessed_by = ?,
                actual_time = CONVERT(time, DATEADD(HOUR, 8, GETDATE())),
                remarks = ?
            WHERE log_id = ?
        """,
            given_by,
            witnessed_by,
            remarks,
            log_id
        )

        connection.commit()

        return {
            "message": "Medication administered successfully.",
            "log_id": log_id
        }

    except Exception as error:
        print(
            f"ERROR administering medication {log_id}:",
            error
        )

        if connection:
            try:
                connection.rollback()
            except Exception:
                pass

        raise HTTPException(
            status_code=503,
            detail="Medication system is temporarily unavailable."
        )

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()


# =========================================================
# CANCEL MEDICATION
# =========================================================

@app.put("/medications/{log_id}/cancel")
def cancel_medication(
    log_id: str,
    cancellation_reason: str,
    remarks: str = ""
):

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT status
            FROM MedicationLogs
            WHERE log_id = ?
        """, log_id)

        row = cursor.fetchone()

        if row is None:
            return {
                "error": "Medication log not found."
            }

        if row.status != "Pending":
            return {
                "error": "This medication has already been completed."
            }

        valid_reasons = [
            "Absent",
            "Early Dismissal",
            "Other"
        ]

        if cancellation_reason not in valid_reasons:
            return {
                "error": "Invalid cancellation reason."
            }

        cursor.execute("""
            UPDATE MedicationLogs
            SET
                status = 'Cancelled',
                cancellation_reason = ?,
                remarks = ?
            WHERE log_id = ?
        """,
            cancellation_reason,
            remarks,
            log_id
        )

        connection.commit()

        return {
            "message": "Medication cancelled successfully.",
            "log_id": log_id,
            "reason": cancellation_reason
        }

    except Exception as error:
        print(
            f"ERROR cancelling medication {log_id}:",
            error
        )

        if connection:
            try:
                connection.rollback()
            except Exception:
                pass

        raise HTTPException(
            status_code=503,
            detail="Medication system is temporarily unavailable."
        )

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()


# =========================================================
# GET MEDICATIONS FOR A TRAINEE
# =========================================================

@app.get("/trainees/{trainee_id}/medications")
def get_trainee_medications(trainee_id: str):

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                medication_id,
                medication_name,
                dosage,
                frequency,
                scheduled_time,
                instructions
            FROM Medications
            WHERE trainee_id = ?
              AND active = 1
            ORDER BY scheduled_time
        """, trainee_id)

        rows = cursor.fetchall()

        medications = []

        for row in rows:

            medications.append({
                "medication_id": row.medication_id,
                "medication_name": row.medication_name,
                "dosage": row.dosage,
                "frequency": row.frequency,
                "scheduled_time": str(row.scheduled_time),
                "instructions": row.instructions
            })

        return medications

    except Exception as error:
        print("ERROR loading trainee medications:", error)

        raise HTTPException(
            status_code=503,
            detail="Medication system is temporarily unavailable."
        )

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()


# =========================================================
# GET MEDICATION HISTORY
# =========================================================

@app.get("/history/{trainee_id}/{medication_id}")
def get_medication_history(
    trainee_id: str,
    medication_id: str
):

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                ml.log_id,
                ml.administration_date,
                ml.scheduled_time,
                ml.status,
                ml.actual_time,
                ml.given_by,
                given_staff.name AS given_by_name,
                ml.witnessed_by,
                witnessed_staff.name AS witnessed_by_name,
                ml.cancellation_reason,
                ml.remarks

            FROM MedicationLogs ml

            LEFT JOIN Staff given_staff
                ON ml.given_by = given_staff.staff_id

            LEFT JOIN Staff witnessed_staff
                ON ml.witnessed_by = witnessed_staff.staff_id

            WHERE ml.trainee_id = ?
              AND ml.medication_id = ?

            ORDER BY
                ml.administration_date DESC,
                ml.scheduled_time DESC
        """,
            trainee_id,
            medication_id
        )

        rows = cursor.fetchall()

        history = []

        for row in rows:

            history.append({

                "log_id": row.log_id,

                "date": str(
                    row.administration_date
                ),

                "scheduled_time": str(
                    row.scheduled_time
                ),

                "status": row.status,

                "actual_time": (
                    row.actual_time.isoformat()
                    if row.actual_time
                    else None
                ),

                "given_by": row.given_by_name,

                "witnessed_by": row.witnessed_by_name,

                "cancellation_reason":
                    row.cancellation_reason,

                "remarks":
                    row.remarks
            })

        return history

    except Exception as error:
        print("ERROR loading medication history:", error)

        raise HTTPException(
            status_code=503,
            detail="Medication system is temporarily unavailable."
        )

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()


# =========================================================
# HEALTH CHECK
# =========================================================

@app.get("/health")
def health_check():
    return {
        "status": "ok"
    }