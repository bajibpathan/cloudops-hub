import os

import psycopg
from flask import Flask, jsonify, request
from psycopg.rows import dict_row

app = Flask(__name__)


def get_db_connection():
    return psycopg.connect(
        host=os.environ["DB_HOST"],
        port=os.environ.get("DB_PORT", "5432"),
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        row_factory=dict_row,
    )


@app.get("/health")
def health():
    return jsonify({
        "status": "healthy",
        "service": "cloudops-hub-backend"
    }), 200


@app.get("/api/applications")
def get_applications():
    try:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT
                        id,
                        name,
                        description,
                        owner_team,
                        environment,
                        status,
                        created_at,
                        updated_at
                    FROM applications
                    ORDER BY id;
                """)

                applications = cursor.fetchall()

        return jsonify(applications), 200

    except Exception as error:
        app.logger.exception("Failed to retrieve applications")
        return jsonify({
            "error": "Unable to retrieve applications"
        }), 500


@app.post("/api/applications")
def create_application():
    data = request.get_json(silent=True) or {}

    required_fields = [
        "name",
        "owner_team",
        "environment",
        "status",
    ]

    missing_fields = [
        field for field in required_fields
        if not data.get(field)
    ]

    if missing_fields:
        return jsonify({
            "error": "Missing required fields",
            "fields": missing_fields,
        }), 400

    try:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO applications (
                        name,
                        description,
                        owner_team,
                        environment,
                        status
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING
                        id,
                        name,
                        description,
                        owner_team,
                        environment,
                        status,
                        created_at,
                        updated_at;
                """, (
                    data["name"],
                    data.get("description"),
                    data["owner_team"],
                    data["environment"],
                    data["status"],
                ))

                application = cursor.fetchone()

        return jsonify(application), 201

    except Exception:
        app.logger.exception("Failed to create application")
        return jsonify({
            "error": "Unable to create application"
        }), 500


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False,
    )