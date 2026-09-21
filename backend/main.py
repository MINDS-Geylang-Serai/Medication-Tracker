from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.database import get_connection

app = FastAPI()

class LoginRequest(BaseModel):
    staff_id: str


@app.post("/login")
def login(request: LoginRequest):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT staff_id, name, role, unit
        FROM Staff
        WHERE staff_id = ?
          AND active = 1
    """, request.staff_id)

    row = cursor.fetchone()

    cursor.close()
    connection.close()

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


# Allow the frontend to communicate with the backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------
# FRONTEND
# ---------------------------------------------------------

app.mount(
    "/frontend",
    StaticFiles(directory="frontend"),
    name="frontend"
)

@app.get("/")
def home():
    return FileResponse("frontend/index.html")


# ---------------------------------------------------------
# GET MEDICATION LOGS
# ---------------------------------------------------------

@app.get("/medications")
def get_medications():

    connection = get_connection()
    cursor = connection.cursor()

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

        ORDER BY
            ml.scheduled_time ASC
    """)

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

    cursor.close()
    connection.close()

    return medications


# ---------------------------------------------------------
# GET STAFF
# ---------------------------------------------------------

@app.get("/staff")
def get_staff():

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

    cursor.close()
    connection.close()

    return staff


# ---------------------------------------------------------
# ADMINISTER MEDICATION
# ---------------------------------------------------------

@app.put("/medications/{log_id}/administer")
def administer_medication(
    log_id: str,
    witnessed_by: str,
    remarks: str = ""
):

    connection = get_connection()
    cursor = connection.cursor()

    # Make sure the medication is still pending
    cursor.execute("""
        SELECT status
        FROM MedicationLogs
        WHERE log_id = ?
    """, log_id)

    row = cursor.fetchone()

    if row is None:
        cursor.close()
        connection.close()

        return {
            "error": "Medication log not found."
        }

    if row.status != "Pending":
        cursor.close()
        connection.close()

        return {
            "error": "This medication has already been completed."
        }

    # For this prototype, S002 is the current Training Officer.
    # Later this will come from the authenticated user.
    given_by = "S002"

    cursor.execute("""
        UPDATE MedicationLogs
        SET
            status = 'Administered',
            given_by = ?,
            witnessed_by = ?,
            actual_time = GETDATE(),
            remarks = ?
        WHERE log_id = ?
    """,
        given_by,
        witnessed_by,
        remarks,
        log_id
    )

    connection.commit()

    cursor.close()
    connection.close()

    return {
        "message": "Medication administered successfully.",
        "log_id": log_id
    }


# ---------------------------------------------------------
# CANCEL MEDICATION
# ---------------------------------------------------------

@app.put("/medications/{log_id}/cancel")
def cancel_medication(
    log_id: str,
    cancellation_reason: str,
    remarks: str = ""
):

    connection = get_connection()
    cursor = connection.cursor()

    # Make sure the medication is still pending
    cursor.execute("""
        SELECT status
        FROM MedicationLogs
        WHERE log_id = ?
    """, log_id)

    row = cursor.fetchone()

    if row is None:
        cursor.close()
        connection.close()

        return {
            "error": "Medication log not found."
        }

    if row.status != "Pending":
        cursor.close()
        connection.close()

        return {
            "error": "This medication has already been completed."
        }

    # Validate cancellation reason
    valid_reasons = [
        "Absent",
        "Early Dismissal",
        "Other"
    ]

    if cancellation_reason not in valid_reasons:
        cursor.close()
        connection.close()

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

    cursor.close()
    connection.close()

    return {
        "message": "Medication cancelled successfully.",
        "log_id": log_id,
        "reason": cancellation_reason
    }

# ---------------------------------------------------------
# GET TRAINEES FOR HISTORY
# ---------------------------------------------------------

@app.get("/trainees")
def get_trainees():

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

    cursor.close()
    connection.close()

    return trainees


# ---------------------------------------------------------
# GET MEDICATIONS FOR A TRAINEE
# ---------------------------------------------------------

@app.get("/trainees/{trainee_id}/medications")
def get_trainee_medications(trainee_id: str):

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

    cursor.close()
    connection.close()

    return medications


# ---------------------------------------------------------
# GET MEDICATION HISTORY
# ---------------------------------------------------------

@app.get("/history/{trainee_id}/{medication_id}")
def get_medication_history(
    trainee_id: str,
    medication_id: str
):

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

    cursor.close()
    connection.close()

    return history