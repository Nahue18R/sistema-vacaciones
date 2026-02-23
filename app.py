import streamlit as st
from streamlit_gsheets import GSheetsConnection
from streamlit_calendar import calendar
import pandas as pd
from datetime import timedelta, date, datetime
import requests
import time
import os
import threading
from dateutil.relativedelta import relativedelta

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Sistema RRHH - Open25", layout="wide", initial_sidebar_state="expanded")

# ==========================================
# ⚠️ TUS LINKS DE NGROK
# ==========================================
BASE_URL = "https://spring-hedgeless-eccentrically.ngrok-free.dev" 
WEBHOOK_SOLICITUD = f"{BASE_URL}/webhook/solicitud-vacaciones"
WEBHOOK_APROBACION = f"{BASE_URL}/webhook/solicitud-aprobada"

# --- ESTILOS CSS ---
st.markdown("""
    <style>
    .stMetric {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        padding: 15px;
        border-radius: 12px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }
    .nombre-titulo {
        font-size: 28px !important;
        font-weight: 800 !important;
        color: #1e293b;
        margin-bottom: 0px;
    }
    .puesto-subtitulo {
        font-size: 16px;
        color: #64748b;
        font-weight: 500;
        margin-bottom: 15px;
    }
    .stButton button {
        border-radius: 8px;
        font-weight: 600;
    }
    /* Ajuste para el calendario */
    .fc-event-title {
        font-weight: bold !important;
        font-size: 14px !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- LOGIN ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    
# --- ESTADO PARA FILTRO VISUAL (VELOCIDAD DE INTERFAZ) ---
if 'filas_procesadas' not in st.session_state:
    st.session_state.filas_procesadas = []

def login():
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        st.markdown("## 🔒 Acceso Supervisores")
        with st.form("login"):
            usr = st.text_input("Usuario")
            pwd = st.text_input("Contraseña", type="password")
            if st.form_submit_button("Ingresar", use_container_width=True):
                if usr == "OFICINA" and pwd == "123456":
                    st.session_state.logged_in = True
                    st.rerun()
                else:
                    st.error("Credenciales incorrectas")

if not st.session_state.logged_in:
    login()
    st.stop()

# --- 1. CONEXIÓN Y DATOS ---
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=60)
def cargar_datos():
    try:
        # AQUÍ ESTÁ LA MAGIA: ttl=0 obliga a que no use su memoria secreta
        df_emp = conn.read(worksheet="Empleados", ttl=0)
        df_sol = conn.read(worksheet="Solicitudes", ttl=0)

        df_emp.columns = df_emp.columns.str.strip()
        df_sol.columns = df_sol.columns.str.strip()
        
        # Blindaje de columnas
        cols_requeridas = [
            "ID_Solicitud", "ID_Empleado", "Nombre_Empleado", "Tipo_Ausencia", 
            "Fecha_Inicio", "Fecha_Fin", "Total_Dias_Habiles", 
            "Sustituto_Asignado", "Estado", "Motivo_Comentario"
        ]
        for col in cols_requeridas:
            if col not in df_sol.columns:
                df_sol[col] = None

        # Formateos
        df_emp['Fecha_Ingreso'] = pd.to_datetime(df_emp['Fecha_Ingreso'], dayfirst=True, errors='coerce')
        df_emp['Dias_Restantes'] = pd.to_numeric(df_emp['Dias_Restantes'], errors='coerce').fillna(0)
        df_emp['ID_Empleado'] = pd.to_numeric(df_emp['ID_Empleado'], errors='coerce').fillna(0).astype(int).astype(str)

        return df_emp, df_sol

    except Exception as e:
        st.error(f"Error de conexión con Google Sheets: {e}")
        return None, None

df_empleados, df_solicitudes = cargar_datos()

if df_empleados is None:
    st.stop()

# --- 2. FUNCIONES ---

def enviar_webhook_background(url, payload):
    """Envía el webhook en un hilo separado (súper rápido)"""
    def _send():
        try:
            requests.post(url, json=payload, timeout=4)
        except: pass
    
    hilo = threading.Thread(target=_send)
    hilo.start()

def calcular_dias_corridos(inicio, fin):
    delta = fin - inicio
    return delta.days + 1 

def calcular_antiguedad_texto(fecha_inicio):
    if pd.isna(fecha_inicio): return "⚠️ Revisar fecha en Excel"
    hoy = datetime.now()
    diferencia = relativedelta(hoy, fecha_inicio)
    texto = []
    if diferencia.years > 0: texto.append(f"{diferencia.years} años")
    if diferencia.months > 0: texto.append(f"{diferencia.months} meses")
    if not texto: return "Reciente ingreso"
    return " hace " + " y ".join(texto)

def obtener_foto(legajo):
    extensiones = ['.jpg', '.jpeg', '.png', '.JPG', '.PNG']
    for ext in extensiones:
        archivo = f"{legajo}{ext}"
        if os.path.exists(archivo): return archivo
    return "https://cdn-icons-png.flaticon.com/512/3135/3135715.png"

# --- 3. MENÚ LATERAL ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/9320/9320295.png", width=60)
    st.title("Panel RRHH")
    menu = st.radio("Navegación", ["👥 Gestión de Personal", "✅ Aprobaciones", "📅 Calendario"])
    st.markdown("---")
    if st.button("Salir"):
        st.session_state.logged_in = False
        st.session_state.filas_procesadas = [] # Limpiar cache visual al salir
        st.rerun()

# =======================================================
# PÁGINA 1: GESTIÓN
# =======================================================
if menu == "👥 Gestión de Personal":
    st.header("Gestión de Colaboradores")
    
    lista_nombres = df_empleados['Nombre_Completo'].unique()
    col_sel, _ = st.columns([1, 2])
    with col_sel:
        empleado_selec = st.selectbox("Buscar Colaborador:", lista_nombres)

    datos_emp = df_empleados[df_empleados['Nombre_Completo'] == empleado_selec].iloc[0]

    st.markdown("---")
    col_foto, col_info, col_kpi = st.columns([1, 3, 2])
    
    with col_foto:
        legajo_actual = str(datos_emp['ID_Empleado'])
        st.image(obtener_foto(legajo_actual), width=130)
        link_docs = datos_emp.get('Link_Legajo', '#')
        if pd.notna(link_docs) and str(link_docs).strip() not in ["", "#"]:
             st.link_button("📂 Ver Legajo", link_docs, use_container_width=True)

    with col_info:
        st.markdown(f'<div class="nombre-titulo">{datos_emp["Nombre_Completo"]}</div>', unsafe_allow_html=True)
        fecha_ing = datos_emp.get('Fecha_Ingreso', pd.NaT)
        
        if pd.isna(fecha_ing):
             fecha_texto = "Sin dato"
             texto_antiguedad = "-"
        else:
             fecha_texto = fecha_ing.strftime('%d/%m/%Y')
             texto_antiguedad = calcular_antiguedad_texto(fecha_ing)
        
        st.markdown(f'<div class="puesto-subtitulo">Legajo: {datos_emp["ID_Empleado"]} | Ingreso: {fecha_texto}</div>', unsafe_allow_html=True)
        
        if texto_antiguedad != "-": st.success(f"🏅 **Antigüedad:** {texto_antiguedad}")
        else: st.warning("⚠️ No se pudo calcular antigüedad")
        
        st.info(f"ℹ️ **Desglose:** {datos_emp.get('Detalle_Vacaciones', 'Sin detalle')}")

    with col_kpi:
        st.metric("Saldo Disponible", f"{int(datos_emp['Dias_Restantes'])} días")
        
        # Filtro visual también aquí
        pend_base = df_solicitudes[(df_solicitudes['Nombre_Empleado'] == empleado_selec) & (df_solicitudes['Estado'] == 'Pendiente')]
        pend_base = pend_base[~pend_base.index.isin(st.session_state.filas_procesadas)]
        
        st.metric("Solicitudes Activas", len(pend_base))

    st.markdown("---")

    c_form, c_hist = st.columns([1, 1.3])
    with c_form:
        with st.container(border=True):
            st.subheader("📝 Nueva Solicitud")
            with st.form("form_vacs"):
                tipo = st.selectbox("Tipo", ["Vacaciones", "Enfermedad", "Trámite", "Home Office", "Licencia"])
                c1, c2 = st.columns(2)
                fi = c1.date_input("Desde", date.today())
                ff = c2.date_input("Hasta", date.today())
                
                l_sust = df_empleados[df_empleados['Nombre_Completo'] != empleado_selec]['Nombre_Completo'].tolist()
                l_sust.insert(0, "No precisa")
                sust = st.selectbox("Sustituto", l_sust)
                motivo = st.text_area("Observaciones")
                
                dias = calcular_dias_corridos(fi, ff)
                st.write(f"📅 Días totales a descontar: **{dias}**")
                
                if st.form_submit_button("Guardar", use_container_width=True):
                    if dias <= 0: st.error("Fechas incorrectas")
                    elif tipo == "Vacaciones" and dias > datos_emp['Dias_Restantes']: st.error("Sin saldo suficiente")
                    else:
                        with st.spinner("🚀 Enviando solicitud..."):
                            # 1. PREPARAR DATOS (Instantáneo)
                            nuevo = pd.DataFrame([{ 
                                "ID_Solicitud": f"REQ-{len(df_solicitudes)+1000}",
                                "ID_Empleado": datos_emp['ID_Empleado'],
                                "Nombre_Empleado": empleado_selec,
                                "Tipo_Ausencia": tipo,
                                "Fecha_Inicio": fi.strftime("%Y-%m-%d"),
                                "Fecha_Fin": ff.strftime("%Y-%m-%d"),
                                "Total_Dias_Habiles": dias,
                                "Sustituto_Asignado": sust,
                                "Estado": "Pendiente",
                                "Motivo_Comentario": motivo
                            }])
                            
                            ret = ff + timedelta(days=1)
                            req_data = {
                                "legajo": str(datos_emp['ID_Empleado']),
                                "nombre": empleado_selec,
                                "tipo": tipo,
                                "desde": fi.strftime("%d/%m/%Y"),
                                "hasta": ff.strftime("%d/%m/%Y"),
                                "dia_vuelve": ret.strftime("%d/%m/%Y"),
                                "dias_tomados": int(dias),
                                "dias_restantes": int(datos_emp['Dias_Restantes'] - dias),
                                "email_jefe": "nruiz@open25.com.ar"
                            }

                            # 2. DISPARAR MAIL PRIMERO (Para que salga YA, mientras se guarda lo demás)
                            enviar_webhook_background(WEBHOOK_SOLICITUD, req_data)
                            
                            # 3. GUARDAR EN EXCEL (Esto es lo lento, pero el mail ya salió)
                            conn.update(worksheet="Solicitudes", data=pd.concat([df_solicitudes, nuevo], ignore_index=True))
                            
                            # 4. LIMPIEZA
                            cargar_datos.clear()
                            st.success("¡Registrado!")
                            time.sleep(0.5) 
                            st.rerun()

    with c_hist:
        st.subheader("Historial")
        h = df_solicitudes[df_solicitudes['Nombre_Empleado'] == empleado_selec].sort_index(ascending=False)
        if not h.empty:
            st.dataframe(
                h[['Fecha_Inicio', 'Fecha_Fin', 'Total_Dias_Habiles', 'Tipo_Ausencia', 'Estado']], 
                column_config={"Total_Dias_Habiles": "Días"},
                hide_index=True, 
                use_container_width=True
            )
        else: st.info("Sin registros.")

# =======================================================
# PÁGINA 2: APROBACIONES
# =======================================================
elif menu == "✅ Aprobaciones":
    st.header("Centro de Aprobaciones")
    
    # 1. Obtenemos las pendientes originales de los datos
    pend = df_solicitudes[df_solicitudes['Estado'] == 'Pendiente']
    
    # 2. APLICAMOS EL TRUCO: Filtramos las que ya tocamos en esta sesión
    pend = pend[~pend.index.isin(st.session_state.filas_procesadas)]
    
    if pend.empty: 
        st.success("Todo al día 🚀")
    else:
        st.write(f"Tienes {len(pend)} solicitudes pendientes.")
        for i, r in pend.iterrows():
            with st.container(border=True):
                c1, c2, c3 = st.columns([2,2,1])
                c1.markdown(f"**{r['Nombre_Empleado']}**")
                c1.caption(f"Tipo: {r['Tipo_Ausencia']}")
                c1.text(f"Legajo: {r['ID_Empleado']}")
                
                c2.write(f"📅 **{r['Fecha_Inicio']}** al **{r['Fecha_Fin']}**")
                c2.info(f"⏳ Días a descontar: {r['Total_Dias_Habiles']}")
                
                if c3.button("✅ Aprobar", key=f"y{i}", use_container_width=True):
                    # Ocultar YA
                    st.session_state.filas_procesadas.append(i)
                    
                    with st.spinner("Procesando..."):
                        try:
                            # 1. PREPARAR DATOS (Instantáneo)
                            fecha_ret = pd.to_datetime(r['Fecha_Fin']) + timedelta(days=1)
                            
                            # AQUÍ TAMBIÉN AGREGAMOS ttl=0 para leer el saldo fresco sin memoria secreta
                            df_fresh = conn.read(worksheet="Empleados", ttl=0)
                            df_fresh.columns = df_fresh.columns.str.strip()
                            
                            id_buscado = str(r['ID_Empleado']).strip().replace(".0", "")
                            df_fresh['ID_Empleado'] = df_fresh['ID_Empleado'].astype(str).str.strip().str.replace(".0", "", regex=False)
                            idx = df_fresh[df_fresh['ID_Empleado'] == id_buscado].index
                            
                            nuevo_saldo = 0
                            if not idx.empty:
                                saldo_anterior = pd.to_numeric(df_fresh.at[idx[0], 'Dias_Restantes'], errors='coerce')
                                if pd.isna(saldo_anterior): saldo_anterior = 0
                                nuevo_saldo = saldo_anterior - r['Total_Dias_Habiles']

                                payload = {
                                    "legajo": str(r['ID_Empleado']),
                                    "nombre": r['Nombre_Empleado'],
                                    "tipo": r['Tipo_Ausencia'],
                                    "desde": pd.to_datetime(r['Fecha_Inicio']).strftime("%d/%m/%Y"),
                                    "hasta": pd.to_datetime(r['Fecha_Fin']).strftime("%d/%m/%Y"),
                                    "dia_vuelve": fecha_ret.strftime("%d/%m/%Y"),
                                    "dias_tomados": int(r['Total_Dias_Habiles']),
                                    "dias_restantes": int(nuevo_saldo),
                                    "email_jefe": "nruiz@open25.com.ar"
                                }
                                
                                # 2. DISPARAR MAIL YA (Prioridad total)
                                enviar_webhook_background(WEBHOOK_APROBACION, payload)

                                # 3. ACTUALIZAR GOOGLE 
                                df_fresh.at[idx[0], 'Dias_Restantes'] = nuevo_saldo
                                conn.update(worksheet="Empleados", data=df_fresh)
                                
                                df_solicitudes.at[i, 'Estado'] = 'Aprobado'
                                conn.update(worksheet="Solicitudes", data=df_solicitudes)
                                
                                cargar_datos.clear()
                                st.toast("✅ Aprobado")
                                time.sleep(0.5)
                                st.rerun() 
                            else:
                                st.error(f"❌ Error: No encontré el legajo {id_buscado}.")
                        except Exception as e:
                            st.error(f"Error técnico: {e}")
                    
                if c3.button("❌ Rechazar", key=f"n{i}", use_container_width=True):
                    # Ocultar visualmente YA
                    st.session_state.filas_procesadas.append(i)
                    
                    df_solicitudes.at[i, 'Estado'] = 'Rechazado'
                    conn.update(worksheet="Solicitudes", data=df_solicitudes)
                    
                    cargar_datos.clear()
                    st.toast("❌ Rechazado")
                    time.sleep(0.5)
                    st.rerun()

# =======================================================
# PÁGINA 3: CALENDARIO
# =======================================================
elif menu == "📅 Calendario":
    st.header("📅 Calendario de Ausencias")
    
    c1, c2, c3 = st.columns(3)
    c1.markdown("🟠 **Pendiente**")
    c2.markdown("🟢 **Aprobado**")
    c3.markdown("🔴 **Rechazado**")
    st.markdown("---")

    if not df_solicitudes.empty:
        eventos_calendario = []
        for _, r in df_solicitudes.iterrows():
            if pd.notna(r['Fecha_Inicio']) and pd.notna(r['Fecha_Fin']):
                color_evento = "#3B82F6"
                if r['Estado'] == 'Pendiente': color_evento = "#F59E0B"
                elif r['Estado'] == 'Aprobado': color_evento = "#10B981"
                elif r['Estado'] == 'Rechazado': color_evento = "#EF4444"
                
                try:
                    fin_visual = pd.to_datetime(r['Fecha_Fin']) + timedelta(days=1)
                    eventos_calendario.append({
                        "title": f"{r['Nombre_Empleado']} ({r['Tipo_Ausencia']})",
                        "start": str(r['Fecha_Inicio']),
                        "end": fin_visual.strftime("%Y-%m-%d"),
                        "backgroundColor": color_evento,
                        "borderColor": color_evento,
                        "allDay": True
                    })
                except: pass

        calendar_options = {
            "editable": False, 
            "navLinks": False,
            "headerToolbar": {
                "left": "today prev,next",
                "center": "title",
                "right": "dayGridMonth,listMonth"
            },
            "initialView": "dayGridMonth",
            "locale": "es",
            "buttonText": {
                "today": "Hoy",
                "month": "Mes",
                "list": "Lista"
            }
        }
        calendar(events=eventos_calendario, options=calendar_options)
    else:
        st.info("No hay vacaciones cargadas.")

