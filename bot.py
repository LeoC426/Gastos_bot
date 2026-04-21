# bot.py
import pandas as pd
from io import BytesIO
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes

from config import TOKEN
import database

user_states = {}

database.create_table()


def clasificar(nombre):
    nombre = nombre.lower()

    if any(x in nombre for x in ["taco", "comida", "pizza"]):
        return "Alimentación"
    elif any(x in nombre for x in ["uber", "taxi", "bus"]):
        return "Transporte"
    elif any(x in nombre for x in ["netflix", "spotify"]):
        return "Entretenimiento"
    else:
        return "Otros"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nombre_usuario = update.effective_user.first_name

    await update.message.reply_text(
        f"Hola, {nombre_usuario}\n\n"
        "Soy tu bot de gastos creado por Leo\n\n"
        "Formato para ingresar gastos:\n"
        "Nombre, Prioridad (Alta/Media/Baja), Monto aproximado\n\n"
        "Ejemplo:\n"
        "Comida, Alta, 120\n\n"
        "Usa /update_gasto cuando hayas completado ese gasto\n"
        "Formato para actualizar gastos:\n"
        "Nombre, Precio real\n"
        "Ejemplo:\n"
        "Comida, 400"
        "Puedes pedir tus gastos desglosados con /exportar\n\n"
        "Borrar un gasto con /borrar_gasto\n"
        "Formato:\n"
        "Gasto, Razón(no necesario, otro)\n"
        "Ejemplo:\n"
        "Comida, no necesario"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    # UPDATE GASTO
    if user_states.get(user_id) == "esperando_update":
        try:
            nombre, precio_real = [x.strip() for x in text.split(",")]
            precio_real = float(precio_real)
        except:
            await update.message.reply_text("Formato incorrecto. Usa: Nombre, Precio_real")
            return
        updated = database.update_gasto(user_id, nombre, precio_real)
        if updated:
            await update.message.reply_text(
                f"Actualizado:\n{updated[0]}\n\n"
                f"Estimado: ${updated[1]}\nReal: ${precio_real}"
                )
        else:
            await update.message.reply_text("No se encontró el gasto.")
        user_states.pop(user_id)
        return

    try:
        # CASO BORRAR
        if user_states.get(user_id) == "esperando_borrado":

            nombre, razon = [x.strip() for x in text.split(",")]

            if razon.lower() not in ["no necesario", "otro"]:
                raise ValueError()

            deleted = database.delete_gasto(user_id, nombre)

            if deleted:
                await update.message.reply_text(
                    f"Eliminado:\n{deleted[0]} - ${deleted[1]}\n\n"
                    f"Razón: {razon}"
                )
            else:
                await update.message.reply_text(
                    "No se encontró ese gasto."
                )

            user_states.pop(user_id)
            return

        # CASO NORMAL (guardar)
        nombre, prioridad, monto = [x.strip() for x in text.split(",")]

        if prioridad.lower() not in ["alta", "media", "baja"]:
            raise ValueError()

        monto = float(monto)
        categoria = clasificar(nombre)

        database.insert_gasto(user_id, nombre, prioridad, monto, categoria)

        await update.message.reply_text(
            f"Guardado\n\n"
            f"{nombre} | {categoria} | ${monto}"
        )

    except:
        await update.message.reply_text(
            "Formato incorrecto\n\n"
            "Guardar:\nNombre, Prioridad, Monto aproximado\n\n"
            "Borrar:\nNombre, Razón\n\n"
            "Razones: No necesario / Otro"
        )


async def total(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    total = database.get_total(user_id)

    await update.message.reply_text(f"Tu total: ${total}")


async def categorias(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = database.get_by_category(user_id)

    if not data:
        await update.message.reply_text("No tienes gastos aún.")
        return

    msg = "Tus gastos por categoría:\n\n"

    for cat, total in data:
        msg += f"{cat}: ${total}\n"

    await update.message.reply_text(msg)

async def exportar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = database.get_all_by_user(user_id)

    if not data:
        await update.message.reply_text("No tienes gastos para exportar.")
        return

    # DataFrame
    df = pd.DataFrame(data, columns=[
        "Nombre", "Prioridad", "Monto", "Categoría", "Fecha",
        "Cumplido", "Precio Real"
    ])

    df["Cumplido"] = df["Cumplido"].map({True: "Sí", False: "No"})
    df["Precio Real"] = df["Precio Real"].fillna(0)
    df["Diferencia"] = df["Precio Real"] - df["Monto"]

    filename = f"gastos_{user_id}.xlsx"

    # Crear en memoria
    file_stream = BytesIO()
    df.to_excel(file_stream, index=False)
    file_stream.seek(0)

    # Aplicar formato desde memoria
    wb = load_workbook(file_stream)
    ws = wb.active

    header_fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
    alta_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
    media_fill = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")
    baja_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")

    # Header
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")

    # Auto width
    for col in ws.columns:
        max_length = 0
        col_letter = col[0].column_letter

        for cell in col:
            if cell.value:
                max_length = max(max_length, len(str(cell.value)))

        ws.column_dimensions[col_letter].width = max_length + 2

    # Colores por prioridad
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        prioridad = str(row[1].value).lower()

        fill = None
        if prioridad == "alta":
            fill = alta_fill
        elif prioridad == "media":
            fill = media_fill
        elif prioridad == "baja":
            fill = baja_fill

        if fill:
            for cell in row:
                cell.fill = fill

    # Resumen
    last_row = ws.max_row + 2

    ws[f"A{last_row}"] = "RESUMEN"
    ws[f"A{last_row}"].font = Font(bold=True)

    ws[f"A{last_row+1}"] = "Total estimado"
    ws[f"B{last_row+1}"] = df["Monto"].sum()

    ws[f"A{last_row+2}"] = "Total real"
    ws[f"B{last_row+2}"] = df["Precio Real"].sum()

    ws[f"A{last_row+3}"] = "Diferencia total"
    ws[f"B{last_row+3}"] = df["Diferencia"].sum()

    # Guardar otra vez en memoria
    output = BytesIO()
    wb.save(output)
    output.seek(0)

    # Enviar
    await update.message.reply_document(
        document=output,
        filename=filename
    )

async def borrar_gasto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    user_states[user_id] = "esperando_borrado"

    await update.message.reply_text(
        "Borrar gasto\n\n"
        "Formato:\n"
        "Nombre, Razón\n\n"
        "Ejemplo:\n"
        "Uber, No necesario"
    )

async def update_gasto_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    data = database.get_pendientes(user_id)

    if not data:
        await update.message.reply_text("No tienes gastos pendientes")
        return

    mensaje = "Gastos pendientes:\n\n"

    for nombre, monto in data:
        mensaje += f"{nombre} - ${monto}\n"

    mensaje += "\nFormato:\nNombre, Precio_real\nEjemplo:\nUber, 95"

    user_states[user_id] = "esperando_update"

    await update.message.reply_text(mensaje)

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("total", total))
    app.add_handler(CommandHandler("categorias", categorias))
    app.add_handler(CommandHandler("exportar", exportar))
    app.add_handler(CommandHandler("borrar_gasto", borrar_gasto))
    app.add_handler(CommandHandler("update_gasto", update_gasto_cmd))
    app.add_handler(MessageHandler(filters.TEXT, handle_message))
    print("Bot multiusuario corriendo...")
    app.run_polling()

if __name__ == "__main__":
    main()