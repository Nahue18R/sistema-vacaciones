import streamlit as st
from streamlit_gsheets import GSheetsConnection
from streamlit_calendar import calendar
import pandas as pd
from datetime import timedelta, date, datetime
import requests
import time

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Sistema RRHH - Open25", layout="wide", initial_sidebar_state="expanded")

# ==========================================
# ⚠️ TUS LINKS DE NGROK (PÉGALOS AQUÍ)
# ==========================================
# Pega aquí tu link actual (el que termina en .ngrok-free.app o .dev)
# Ejemplo: BASE_URL = "https://spring-hedgeless-eccentrically.ngrok-free.dev "
BASE_URL = "https://spring-hedgeless-eccentrically.ngrok-free.dev" # <--- ¡VERIFICA QUE ESTE SEA EL TUYO ACTUAL!

WEBHOOK_SOLICITUD = f"{BASE_URL}/webhook-test/solicitud-vacaciones"
WEBHOOK_APROBACION = f"{BASE_URL}/webhook-test/solicitud-aprobada"
# ==========================================

# --- ESTILOS CSS PERSONALIZADOS (Look & Feel Kenjo) ---
st.markdown("""
    <style>
    .stMetric {
        background-color: #f9f9f9;
        border: 1px solid #e0e0e0;
        padding: 15px;
        border-radius: 10px;
    }
    .stButton button {
        border-radius: 8px;
    }
    </style>
""", unsafe_allow_html=True)

# --- SISTEMA DE LOGIN ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

def login():
    st.markdown("## 🔒 Acceso Supervisores")
    usr = st.text_input("Usuario")
    pwd = st.text_input("Contraseña", type="password")
    if st.button("Ingresar"):
        if usr == "OFICINA" and pwd == "123456":
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.error("Credenciales incorrectas")

if not st.session_state.logged_in:
    login()
    st.stop() # Detiene la app aquí si no está logueado

# --- 1. CONEXIÓN Y DATOS ---
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    df_empleados = conn.read(worksheet="Empleados", ttl=5)
    df_feriados = conn.read(worksheet="Feriados", ttl=600)
    df_solicitudes = conn.read(worksheet="Solicitudes", ttl=0)

    # Limpieza
    df_empleados.columns = df_empleados.columns.str.strip()
    df_solicitudes.columns = df_solicitudes.columns.str.strip()
    df_feriados['Fecha'] = pd.to_datetime(df_feriados['Fecha'], dayfirst=True, errors='coerce').dt.date
    df_empleados['Dias_Restantes'] = pd.to_numeric(df_empleados['Dias_Restantes'], errors='coerce').fillna(0)
    
    # Aseguramos que ID_Empleado sea string para que no se vea como número con coma
    df_empleados['ID_Empleado'] = df_empleados['ID_Empleado'].astype(str)

except Exception as e:
    st.error(f"⚠️ Error detallado: {e}") # <--- NUEVA: Nos muestra el texto técnico
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

# --- 3. MENÚ LATERAL (Navegación Admin) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/9320/9320295.png", width=60)
    st.title("Panel RRHH")
    st.caption("Modo Supervisor: Activo")
    st.markdown("---")
    
    menu = st.radio("Menú Principal", 
                    ["👥 Gestión de Empleados", 
                     "✅ Aprobaciones Pendientes", 
                     "📅 Calendario Global"],
                    index=0)
    
    st.markdown("---")
    if st.button("Cerrar Sesión"):
        st.session_state.logged_in = False
        st.rerun()

# =======================================================
# PÁGINA 1: GESTIÓN DE EMPLEADOS (Cargar Vacaciones)
# =======================================================
if menu == "👥 Gestión de Empleados":
    st.header("Gestión de Ausencias y Vacaciones")
    
    # --- SELECTOR DE EMPLEADO (Estilo Dashboard) ---
    lista_nombres = df_empleados['Nombre_Completo'].unique()
    
    col_sel, col_vacia = st.columns([1, 2])
    with col_sel:
        empleado_selec = st.selectbox("Buscar Empleado:", lista_nombres)

    # Obtenemos datos del empleado seleccionado
    datos_emp = df_empleados[df_empleados['Nombre_Completo'] == empleado_selec].iloc[0]

    # --- TARJETAS DE INFORMACIÓN (KPIs) ---
    st.markdown("### 📋 Ficha del Colaborador")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Legajo", datos_emp['ID_Empleado'])
    k2.metric("Nombre", datos_emp['Nombre_Completo'])
    k3.metric("Saldo Vacaciones", f"{int(datos_emp['Dias_Restantes'])} días")
    
    # Calculamos solicitudes pendientes de este usuario
    pendientes_emp = len(df_solicitudes[(df_solicitudes['Nombre_Empleado'] == empleado_selec) & (df_solicitudes['Estado'] == 'Pendiente')])
    k4.metric("Solicitudes en curso", pendientes_emp, delta_color="off")

    st.markdown("---")

    # --- FORMULARIO DE CARGA ---
    col_form, col_historial = st.columns([1, 1.2])

    with col_form:
        with st.container(border=True):
            st.subheader("📝 Registrar Nueva Ausencia")
            with st.form("form_admin"):
                tipo = st.selectbox("Tipo de Ausencia", ["Vacaciones", "Enfermedad", "Trámite", "Home Office", "Licencia Especial"])
                
                c1, c2 = st.columns(2)
                fecha_inicio = c1.date_input("Desde", date.today())
                fecha_fin = c2.date_input("Hasta", date.today())
                
                # Lógica de sustitutos: Excluir al propio empleado y agregar opción "Ninguno"
                lista_sustitutos = df_empleados[df_empleados['Nombre_Completo'] != empleado_selec]['Nombre_Completo'].tolist()
                lista_sustitutos.insert(0, "No precisa / Sin sustituto")
                sustituto = st.selectbox("Sustituto Asignado", lista_sustitutos)
                
                motivo = st.text_area("Observaciones / Motivo")
                
                # Cálculo en tiempo real
                lista_feriados = df_feriados['Fecha'].tolist() if not df_feriados.empty else []
                dias_calc = calcular_dias_habiles(fecha_inicio, fecha_fin, lista_feriados)
                st.info(f"📅 Días hábiles a descontar: **{dias_calc}**")
                
                enviar = st.form_submit_button("💾 Registrar Solicitud", use_container_width=True)
                
                if enviar:
                    if dias_calc <= 0:
                        st.error("Error: La fecha fin debe ser mayor a la de inicio.")
                    elif tipo == "Vacaciones" and dias_calc > datos_emp['Dias_Restantes']:
                        st.error("⚠️ El empleado no tiene saldo suficiente.")
                    else:
                        # 1. GUARDAR EN GOOGLE SHEETS
                        nueva_fila = pd.DataFrame([{
                            "ID_Solicitud": f"REQ-{len(df_solicitudes)+1001}",
                            "ID_Empleado": datos_emp['ID_Empleado'],
                            "Nombre_Empleado": empleado_selec,
                            "Tipo_Ausencia": tipo,
                            "Fecha_Inicio": fecha_inicio.strftime("%Y-%m-%d"),
                            "Fecha_Fin": fecha_fin.strftime("%Y-%m-%d"),
                            "Total_Dias_Habiles": dias_calc,
                            "Sustituto_Asignado": sustituto,
                            "Estado": "Pendiente",
                            "Motivo_Comentario": motivo
                        }])
                        updated_df = pd.concat([df_solicitudes, nueva_fila], ignore_index=True)
                        conn.update(worksheet="Solicitudes", data=updated_df)
                        
                        # 2. NOTIFICAR (Para que el jefe apruebe formalmente)
                        try:
                            fecha_retorno = fecha_fin + timedelta(days=1)
                            saldo_futuro = datos_emp['Dias_Restantes'] - dias_calc
                            
                            payload = {
                                "legajo": str(datos_emp['ID_Empleado']),
                                "nombre": empleado_selec,
                                "tipo": tipo,
                                "desde": fecha_inicio.strftime("%d/%m/%Y"),
                                "hasta": fecha_fin.strftime("%d/%m/%Y"),
                                "dia_vuelve": fecha_retorno.strftime("%d/%m/%Y"),
                                "dias_tomados": int(dias_calc),
                                "dias_restantes": int(saldo_futuro),
                                "email_jefe": "nruiz@open25.com.ar" 
                            }
                            requests.post(WEBHOOK_SOLICITUD, json=payload, timeout=3)
                            st.toast("📧 Correo de aprobación enviado.")
                        except:
                            st.warning("Guardado, pero falló el envío del correo.")
                            
                        st.success("Solicitud creada correctamente.")
                        time.sleep(1)
                        st.rerun()

    with col_historial:
        st.subheader(f"Historial: {empleado_selec}")
        historial = df_solicitudes[df_solicitudes['Nombre_Empleado'] == empleado_selec].sort_index(ascending=False)
        
        if not historial.empty:
            st.dataframe(
                historial[['Fecha_Inicio', 'Fecha_Fin', 'Tipo_Ausencia', 'Estado']],
                hide_index=True,
                use_container_width=True
            )
        else:
            st.info("No hay registros previos.")

# =======================================================
# PÁGINA 2: APROBACIONES PENDIENTES
# =======================================================
elif menu == "✅ Aprobaciones Pendientes":
    st.header("Centro de Aprobaciones")
    
    pendientes = df_solicitudes[df_solicitudes['Estado'] == 'Pendiente']
    
    if pendientes.empty:
        st.success("¡Excelente! No hay tareas pendientes.")
    else:
        st.write(f"Tienes **{len(pendientes)}** solicitudes esperando revisión.")
        
        for index, row in pendientes.iterrows():
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 2, 2])
                
                with c1:
                    st.markdown(f"### {row['Nombre_Empleado']}")
                    st.caption(f"Legajo: {row['ID_Empleado']} | Tipo: **{row['Tipo_Ausencia']}**")
                    st.text(f"Motivo: {row['Motivo_Comentario']}")
                
                with c2:
                    st.markdown(f"📅 **{row['Fecha_Inicio']}** al **{row['Fecha_Fin']}**")
                    st.markdown(f"⏳ **{row['Total_Dias_Habiles']} días**")
                    st.caption(f"Sustituto: {row['Sustituto_Asignado']}")
                
                with c3:
                    st.write("Acciones:")
                    col_ok, col_no = st.columns(2)
                    
                    if col_ok.button("✅ Aprobar", key=f"aprob_{index}", use_container_width=True):
                        # 1. Actualizar Estado
                        df_solicitudes.at[index, 'Estado'] = 'Aprobado'
                        conn.update(worksheet="Solicitudes", data=df_solicitudes)
                        
                        # 2. Descontar Saldo
                        emp_idx = df_empleados[df_empleados['ID_Empleado'].astype(str) == str(row['ID_Empleado'])].index
                        if not emp_idx.empty:
                            idx = emp_idx[0]
                            nuevo_saldo = df_empleados.at[idx, 'Dias_Restantes'] - row['Total_Dias_Habiles']
                            df_empleados.at[idx, 'Dias_Restantes'] = nuevo_saldo
                            conn.update(worksheet="Empleados", data=df_empleados)
                        else:
                            nuevo_saldo = 0

                        # 3. Webhook Aprobación
                        try:
                            fecha_ret = pd.to_datetime(row['Fecha_Fin']) + timedelta(days=1)
                            payload = {
                                "legajo": str(row['ID_Empleado']),
                                "nombre": row['Nombre_Empleado'],
                                "tipo": row['Tipo_Ausencia'],
                                "desde": pd.to_datetime(row['Fecha_Inicio']).strftime("%d/%m/%Y"),
                                "hasta": pd.to_datetime(row['Fecha_Fin']).strftime("%d/%m/%Y"),
                                "dia_vuelve": fecha_ret.strftime("%d/%m/%Y"),
                                "dias_tomados": int(row['Total_Dias_Habiles']),
                                "dias_restantes": int(nuevo_saldo),
                                "email_jefe": "nruiz@open25.com.ar"
                            }
                            requests.post(WEBHOOK_APROBACION, json=payload)
                        except:
                            pass
                        
                        st.toast("Solicitud Aprobada")
                        st.rerun()
                        
                    if col_no.button("❌ Rechazar", key=f"rech_{index}", use_container_width=True):
                        df_solicitudes.at[index, 'Estado'] = 'Rechazado'
                        conn.update(worksheet="Solicitudes", data=df_solicitudes)
                        st.toast("Solicitud Rechazada")
                        st.rerun()

# =======================================================
# PÁGINA 3: CALENDARIO GLOBAL
# =======================================================
elif menu == "📅 Calendario Global":
    st.header("Calendario de Equipo")
    
    eventos = []
    if not df_solicitudes.empty:
        for _, row in df_solicitudes.iterrows():
            if pd.notna(row['Fecha_Inicio']):
                color = "#FFA726" if row['Estado'] == 'Pendiente' else "#66BB6A" # Naranja / Verde
                if row['Estado'] == 'Rechazado': color = "#EF5350"
                
                eventos.append({
                    "title": f"{row['Nombre_Empleado']} ({row['Tipo_Ausencia']})",
                    "start": str(row['Fecha_Inicio']),
                    "end": str(pd.to_datetime(row['Fecha_Fin']) + timedelta(days=1)),
                    "color": color,
                    "extendedProps": {"status": row['Estado']}
                })

    # CONFIGURACIÓN EN ESPAÑOL
    calendar_options = {
        "locale": "es",
        "headerToolbar": {
            "left": "prev,next today",
            "center": "title",
            "right": "dayGridMonth,listMonth"
        },
        "buttonText": {
            "today": "Hoy",
            "month": "Mes",
            "list": "Lista"
        },
        "initialView": "dayGridMonth",
    }
    
    calendar(events=eventos, options=calendar_options, custom_css="""
        .fc-event-title {font-weight: bold !important;}
        .fc-toolbar-title {text-transform: capitalize !important;}
    """)
    
    st.caption("Referencias: 🟠 Pendiente de Aprobación | 🟢 Aprobado | 🔴 Rechazado")

