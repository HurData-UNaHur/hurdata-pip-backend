from app.db.connection import get_connection

def resetear_base_datos():
    conn = get_connection()
    cursor = conn.cursor()

    # Desactivar restricciones de claves foráneas
    cursor.execute("PRAGMA foreign_keys = OFF;")

    # Lista de tablas según schema.sql
    tablas = [
        "Resultado_Comision",
        "Comision",
        "Carrera_Materia",
        "Materia",
        "Carrera",
        "Periodo",
        "Estado",
        "Modalidad"
    ]

    for tabla in tablas:
        cursor.execute(f'DELETE FROM "{tabla}";')
        # Reiniciar contadores AUTOINCREMENT
        cursor.execute(f'DELETE FROM sqlite_sequence WHERE name="{tabla}";')

    conn.commit()
    cursor.execute("PRAGMA foreign_keys = ON;")
    conn.close()

    print(f" Base de datos vaciada con éxito. Tablas limpiadas: {tablas}")

if __name__ == "__main__":
    resetear_base_datos()