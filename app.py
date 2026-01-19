import streamlit as st
from streamlit_gsheets import GSheetsConnection
from streamlit_calendar import calendar
import pandas as pd
from datetime import timedelta, date, datetime
import requests # <--- Necesario para hablar con n8n

# Configuración de página estilo "Dashboard"
st.set_page_config(page_title="Portal del Empleado", layout="wide", initial_sidebar_state="expanded")

# --- 1. CONEXIÓN Y DATOS ---
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    df_empleados = conn.read(worksheet="Empleados", ttl=5)
    df_feriados = conn.read(worksheet="Feriados", ttl=600)
    df_solicitudes = conn.read(worksheet="Solicitudes", ttl=0)

    # Limpieza de columnas y tipos de datos
    df_empleados.columns = df_empleados.columns.str.strip()
    df_solicitudes.columns = df_solicitudes.columns.str.strip()
    df_feriados['Fecha'] = pd.to_datetime(df_feriados['Fecha'], dayfirst=True, errors='coerce').dt.date
    df_empleados['Dias_Restantes'] = pd.to_numeric(df_empleados['Dias_Restantes'], errors='coerce').fillna(0)

except Exception as e:
    st.error("Error de conexión. Revisa el archivo secrets.toml y tu internet.")
    st.stop()

# --- 2. FUNCIONES ---
def calcular_dias_habiles(inicio, fin, feriados_lista):
    dias_totales = 0
    fecha_actual = inicio
    while fecha_actual <= fin:
        es_finde = fecha_actual.weekday() >= 5
        es_feriado = fecha_actual in feriados_lista
        if not es_finde and not es_feriado:
            dias_totales += 1
        fecha_actual += timedelta(days=1)
    return dias_totales

# --- 3. BARRA LATERAL (ESTILO KENJO) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=50) 
    st.title("RRHH Portal")
    
    # Simulación de Login
    st.markdown("---")
    st.caption("👤 USUARIO ACTIVO")
    lista_usuarios = df_empleados['Nombre_Completo'].unique() if not df_empleados.empty else []
    usuario_actual = st.selectbox("Selecciona tu nombre", lista_usuarios, index=0)
    
    if usuario_actual:
        datos_usuario = df_empleados[df_empleados['Nombre_Completo'] == usuario_actual].iloc[0]
        st.info(f"Saldo Actual: {int(datos_usuario['Dias_Restantes'])} días")

    # Menú
    st.markdown("---")
    menu = st.radio("Navegación", ["🏠 Mi Espacio", "📅 Calendario Equipo", "🔒 Gestión Supervisor"])

    # Seguridad Supervisor
    clave_supervisor = ""
    if menu == "🔒 Gestión Supervisor":
        st.markdown("---")
        clave_supervisor = st.text_input("Contraseña Admin", type="password")

# --- 4. LÓGICA DE PÁGINAS ---

# === PÁGINA 1: MI ESPACIO (Solicitudes) ===
if menu == "🏠 Mi Espacio":
    st.header(f"👋 Hola, {usuario_actual}")
    st.markdown("Gestiona tus ausencias y notifica automáticamente a tu supervisor.")
    
    col_form, col_hist = st.columns([1, 1.5])
    
    with col_form:
        with st.container(border=True):
            st.subheader("Nueva Solicitud")
            with st.form("form_solicitud"):
                tipo = st.selectbox("Tipo", ["Vacaciones", "Enfermedad", "Trámite", "Home Office"])
                c1, c2 = st.columns(2)
                fecha_inicio = c1.date_input("Desde", date.today())
                fecha_fin = c2.date_input("Hasta", date.today())
                
                posibles_sustitutos = df_empleados[df_empleados['Nombre_Completo'] != usuario_actual]['Nombre_Completo']
                sustituto = st.selectbox("Sustituto", posibles_sustitutos)
                motivo = st.text_area("Comentario / Motivo")
                
                # Cálculo previo
                lista_feriados = df_feriados['Fecha'].tolist() if not df_feriados.empty else []
                dias = calcular_dias_habiles(fecha_inicio, fecha_fin, lista_feriados)
                st.write(f"⏱️ Duración: **{dias} días hábiles**")
                
                submit_btn = st.form_submit_button("🚀 Enviar Solicitud", use_container_width=True)

                if submit_btn:
                    if dias <= 0:
                        st.error("Fechas incorrectas (Fin debe ser mayor a Inicio).")
                    elif tipo == "Vacaciones" and dias > datos_usuario['Dias_Restantes']:
                        st.error("Saldo insuficiente.")
                    else:
                        # 1. GUARDAR EN GOOGLE SHEETS
                        nueva_fila = pd.DataFrame([{
                            "ID_Solicitud": f"REQ-{len(df_solicitudes)+1001}",
                            "ID_Empleado": datos_usuario['ID_Empleado'],
                            "Nombre_Empleado": usuario_actual,
                            "Tipo_Ausencia": tipo,
                            "Fecha_Inicio": fecha_inicio.strftime("%Y-%m-%d"),
                            "Fecha_Fin": fecha_fin.strftime("%Y-%m-%d"),
                            "Total_Dias_Habiles": dias,
                            "Sustituto_Asignado": sustituto,
                            "Estado": "Pendiente",
                            "Motivo_Comentario": motivo
                        }])
                        updated_df = pd.concat([df_solicitudes, nueva_fila], ignore_index=True)
                        conn.update(worksheet="Solicitudes", data=updated_df)

                        # 2. ENVIAR A N8N (Notificación)
                        try:
                            # Cálculos para el cuadro del correo
                            fecha_retorno = fecha_fin + timedelta(days=1)
                            saldo_post_vacaciones = datos_usuario['Dias_Restantes'] - dias
                            
                            payload = {
                                "legajo": str(datos_usuario['ID_Empleado']), # Convertir a string
                                "nombre": usuario_actual,
                                "tipo": tipo,
                                "desde": fecha_inicio.strftime("%d/%m/%Y"),
                                "hasta": fecha_fin.strftime("%d/%m/%Y"),
                                "dia_vuelve": fecha_retorno.strftime("%d/%m/%Y"),
                                "dias_tomados": int(dias),
                                "dias_restantes": int(saldo_post_vacaciones),
                                "email_jefe": "nruiz@open25.com.ar" # <--- TU EMAIL FIJO
                            }
                            
                            # TU URL LOCAL DE N8N
                            webhook_url = "https://spring-hedgeless-eccentrically.ngrok-free.dev/webhook-test/solicitud-vacaciones"
                            
                            requests.post(webhook_url, json=payload, timeout=2) # Timeout corto para no trabar la app
                            st.toast("📧 Notificación enviada a n8n correctamente.")
                            
                        except Exception as e:
                            # Si falla n8n, no rompemos la app, solo avisamos
                            print(f"Error enviando a n8n: {e}")
                            st.toast("⚠️ Solicitud guardada, pero no se pudo notificar a n8n.")

                        st.success("✅ Solicitud registrada con éxito!")
                        st.rerun()

    with col_hist:
        st.subheader("Mis Últimas Solicitudes")
        mis_datos = df_solicitudes[df_solicitudes['Nombre_Empleado'] == usuario_actual].sort_index(ascending=False)
        if not mis_datos.empty:
            st.dataframe(
                mis_datos[['Fecha_Inicio', 'Fecha_Fin', 'Tipo_Ausencia', 'Estado']],
                hide_index=True,
                use_container_width=True
            )
        else:
            st.info("No tienes solicitudes recientes.")

# === PÁGINA 2: CALENDARIO (Visual) ===
elif menu == "📅 Calendario Equipo":
    st.header("Vista de Equipo")
    
    eventos = []
    if not df_solicitudes.empty:
        for _, row in df_solicitudes.iterrows():
            if pd.notna(row['Fecha_Inicio']):
                color = "#FFB067" if row['Estado'] == 'Pendiente' else "#67CBA0"
                if row['Estado'] == 'Rechazado': color = "#FF6C6C"
                
                eventos.append({
                    "title": f"{row['Nombre_Empleado']} - {row['Tipo_Ausencia']}",
                    "start": str(row['Fecha_Inicio']),
                    "end": str(pd.to_datetime(row['Fecha_Fin']) + timedelta(days=1)),
                    "color": color
                })

    calendar(events=eventos, options={"initialView": "dayGridMonth", "headerToolbar": {"left": "prev,next", "center": "title", "right": "dayGridMonth,listWeek"}})
    st.caption("Referencias: 🟠 Pendiente | 🟢 Aprobado | 🔴 Rechazado")

# === PÁGINA 3: SUPERVISOR (Gestión) ===
elif menu == "🔒 Gestión Supervisor":
    if clave_supervisor == "admin123":
        st.header("Panel de Aprobaciones")
        
        pendientes = df_solicitudes[df_solicitudes['Estado'] == 'Pendiente']
        
        if pendientes.empty:
            st.success("¡Todo al día! No hay solicitudes pendientes.")
        else:
            for index, row in pendientes.iterrows():
                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
                    c1.markdown(f"**{row['Nombre_Empleado']}**")
                    c1.caption(f"Legajo: {row['ID_Empleado']} | {row['Tipo_Ausencia']}")
                    c2.text(f"📅 {row['Fecha_Inicio']} -> {row['Fecha_Fin']}")
                    c2.caption(f"Motivo: {row['Motivo_Comentario']}")
                    
                    # --- BOTÓN APROBAR ---
                    if c3.button("✅ Aprobar", key=f"aprob_{index}"):
                        try:
                            # 1. ACTUALIZAR ESTADO EN SOLICITUDES
                            df_solicitudes.at[index, 'Estado'] = 'Aprobado'
                            conn.update(worksheet="Solicitudes", data=df_solicitudes)
                            
                            # 2. DESCONTAR DÍAS DEL SALDO (Hoja Empleados)
                            # Buscamos al empleado por ID para no equivocarnos de nombre
                            emp_id = row['ID_Empleado']
                            dias_a_descontar = row['Total_Dias_Habiles']
                            
                            # Filtramos el índice en el dataframe de empleados
                            idx_empleado = df_empleados[df_empleados['ID_Empleado'] == emp_id].index
                            
                            if not idx_empleado.empty:
                                idx = idx_empleado[0]
                                saldo_actual = df_empleados.at[idx, 'Dias_Restantes']
                                nuevo_saldo = saldo_actual - dias_a_descontar
                                
                                # Guardamos el nuevo saldo en la hoja
                                df_empleados.at[idx, 'Dias_Restantes'] = nuevo_saldo
                                conn.update(worksheet="Empleados", data=df_empleados)
                            else:
                                nuevo_saldo = 0 # Por si no lo encuentra (raro)

                            # 3. ENVIAR A N8N (Notificación de Aprobación)
                            webhook_aprobacion = "https://spring-hedgeless-eccentrically.ngrok-free.dev/webhook-test/solicitud-aprobada"
                            
                            # Calculamos fecha retorno para el cuadro
                            fecha_fin_dt = pd.to_datetime(row['Fecha_Fin'])
                            fecha_retorno = fecha_fin_dt + timedelta(days=1)
                            
                            payload = {
                                "legajo": str(emp_id),
                                "nombre": row['Nombre_Empleado'],
                                "tipo": row['Tipo_Ausencia'],
                                "desde": pd.to_datetime(row['Fecha_Inicio']).strftime("%d/%m/%Y"),
                                "hasta": fecha_fin_dt.strftime("%d/%m/%Y"),
                                "dia_vuelve": fecha_retorno.strftime("%d/%m/%Y"),
                                "dias_tomados": int(dias_a_descontar),
                                "dias_restantes": int(nuevo_saldo),
                                "email_jefe": "nruiz@open25.com.ar" # <--- AQUI TE LLEGA EL COMPROBANTE
                            }
                            
                            requests.post(webhook_aprobacion, json=payload)
                            st.toast(f"✅ Aprobado y enviado a RRHH (Saldo actualizado)")
                            
                        except Exception as e:
                            st.error(f"Error en el proceso: {e}")
                        
                        st.rerun()
                        
                    # --- BOTÓN RECHAZAR ---
                    if c4.button("❌ Rechazar", key=f"rech_{index}"):
                        df_solicitudes.at[index, 'Estado'] = 'Rechazado'
                        conn.update(worksheet="Solicitudes", data=df_solicitudes)
                        st.toast("Solicitud rechazada")
                        st.rerun()
    else:
        if clave_supervisor:
            st.error("Contraseña incorrecta")
        else:

            st.warning("Introduce la contraseña de supervisor en la barra lateral.")
