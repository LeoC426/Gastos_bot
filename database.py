# database.py

import psycopg2
from config import DATABASE_URL


def connect():
    return psycopg2.connect(DATABASE_URL)


def create_table():
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gastos (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            nombre TEXT NOT NULL,
            prioridad TEXT NOT NULL,
            monto FLOAT NOT NULL,
            categoria TEXT,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            cumplido BOOLEAN DEFAULT FALSE,
            precio_real FLOAT
        )
    """)
    cursor.execute("""
        ALTER TABLE gastos
        ADD COLUMN IF NOT EXISTS cumplido BOOLEAN DEFAULT FALSE;
    """)

    cursor.execute("""
        ALTER TABLE gastos
        ADD COLUMN IF NOT EXISTS precio_real FLOAT;
    """)

    conn.commit()
    conn.close()


def insert_gasto(user_id, nombre, prioridad, monto, categoria):
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO gastos (user_id, nombre, prioridad, monto, categoria)
        VALUES (%s, %s, %s, %s, %s)
    """, (user_id, nombre, prioridad, monto, categoria))

    conn.commit()
    conn.close()


def get_total(user_id):
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT SUM(monto) FROM gastos
        WHERE user_id = %s
    """, (user_id,))

    total = cursor.fetchone()[0]

    conn.close()
    return total if total else 0


def get_by_category(user_id):
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT categoria, SUM(monto)
        FROM gastos
        WHERE user_id = %s
        GROUP BY categoria
    """, (user_id,))

    data = cursor.fetchall()

    conn.close()
    return data

def get_all_by_user(user_id):
    """
    Obtiene todos los gastos de un usuario
    """
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT nombre, prioridad, monto, categoria, fecha, cumplido, precio_real
        FROM gastos
        WHERE user_id = %s
        ORDER BY fecha DESC
    """, (user_id,))

    data = cursor.fetchall()

    conn.close()
    return data

def delete_gasto(user_id, nombre):
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM gastos
        WHERE id = (
            SELECT id FROM gastos
            WHERE user_id = %s AND nombre = %s
            ORDER BY fecha DESC
            LIMIT 1
        )
        RETURNING nombre, monto
    """, (user_id, nombre))

    deleted = cursor.fetchone()

    conn.commit()
    conn.close()

    return deleted

def get_pendientes(user_id):
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT nombre, monto
        FROM gastos
        WHERE user_id = %s AND cumplido = FALSE
    """, (user_id,))

    data = cursor.fetchall()
    conn.close()
    return data


def update_gasto(user_id, nombre, precio_real):
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE gastos
        SET cumplido = TRUE,
            precio_real = %s
        WHERE id = (
            SELECT id FROM gastos
            WHERE user_id = %s AND nombre = %s AND cumplido = FALSE
            ORDER BY fecha DESC
            LIMIT 1
        )
        RETURNING nombre, monto
    """, (precio_real, user_id, nombre))

    updated = cursor.fetchone()

    conn.commit()
    conn.close()

    return updated