# ======================================================
# IMPORTS: 
# ======================================================
from flask import Flask, render_template, request, redirect, url_for, flash, session
import json
import pandas as pd
import plotly.express as px
from database import get_db_connection
from datetime import datetime
from dateutil.relativedelta import relativedelta

# Importar Flask-Login
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin

# ======================================================
# INICIALIZACIÓN DE LA APLICACIÓN
# ======================================================
app = Flask(__name__)
app.secret_key = "tu_clave_secreta"  # Necesaria para usar flash y sesiones

# ======================================================
# CONFIGURACIÓN DE FLASK-LOGIN
# ======================================================
login_manager = LoginManager(app)
login_manager.login_view = "login"

# Usuario de ejemplo en memoria (para pruebas)
users = {
    "fpuentem1": {"password": "Ar1$t0t3l3$"}
}

class User(UserMixin):
    def __init__(self, id):
        self.id = id

@login_manager.user_loader
def load_user(user_id):
    if user_id in users:
        return User(user_id)
    return None

# Antes de cada petición, forzamos la autenticación (excepto para 'login' y 'static')
@app.before_request
def require_login():
    if request.endpoint not in ['login', 'static'] and not current_user.is_authenticated:
        return redirect(url_for('login'))

# ======================================================
# FILTRO PERSONALIZADO: Formatea números con comas y sin decimales.
# ======================================================
@app.template_filter('comma')
def comma_filter(value):
    try:
        return "{:,.0f}".format(float(value))
    except (ValueError, TypeError):
        return value

# ======================================================
# FUNCIONES DE CONFIGURACIÓN: Cargar y guardar parámetros.
# ======================================================
def load_config():
    """Carga la configuración desde config.json. Si no existe, retorna valores por defecto."""
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
    except FileNotFoundError:
        config = {
            "risk_threshold": 60,
            "target_exposure": {"Acciones": 40, "Bonos": 30, "Inmuebles": 20, "Otros": 10},
            "current_strategy": "Conservador"
        }
    return config

def save_config(config):
    """Guarda la configuración en config.json."""
    with open('config.json', 'w') as f:
        json.dump(config, f, indent=4)

from functools import wraps
from flask import session  

def portfolio_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'portfolio_id' not in session:
            flash("Debe seleccionar un portafolio antes de continuar.", "warning")
            return redirect(url_for('portfolios'))
        return f(*args, **kwargs)
    return decorated_function

# ======================================================
# FUNCIONES AUXILIARES: Obtener tipo de cambio y normalizar montos.
# ======================================================
def get_exchange_rate(month):
    """
    Obtiene el tipo de cambio (pesos por 1 dólar) para el mes dado desde la tabla exchange_rate.
    Retorna 1 si no se encuentra.
    """
    month = month.strip()
    conn = get_db_connection()
    row = conn.execute('SELECT rate FROM exchange_rate WHERE month = ?', (month,)).fetchone()
    conn.close()
    rate = row['rate'] if row else 1
    print(f"[DEBUG] Tipo de cambio para {month}: {rate}")
    return rate

def normalize_to_mxn(row):
    """
    Convierte el monto a pesos (MXN).
    Si la moneda es USD, multiplica el monto por el tipo de cambio.
    Si la moneda es MXN, devuelve el monto sin cambios.
    """
    if row['currency'] == 'USD':
        rate = get_exchange_rate(row['month'])
        converted = row['amount'] * rate if rate and rate != 0 else row['amount']
        print(f"[DEBUG] Convirtiendo: {row['amount']} USD * {rate} = {converted} MXN")
        return converted
    else:
        return row['amount']

def normalize_to_usd(row):
    """
    Convierte el monto a dólares (USD).
    Si la moneda es MXN, divide el monto por el tipo de cambio.
    Si la moneda es USD, devuelve el monto sin cambios.
    """
    if row['currency'] == 'MXN':
        rate = get_exchange_rate(row['month'])
        converted = row['amount'] / rate if rate and rate != 0 else row['amount']
        print(f"[DEBUG] Convirtiendo: {row['amount']} MXN / {rate} = {converted} USD")
        return converted
    else:
        return row['amount']

# ======================================================
# RUTAS DE LA APLICACIÓN
# ======================================================

# Endpoint de Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username in users and users[username]['password'] == password:
            user = User(username)
            login_user(user)
            flash("Has iniciado sesión correctamente.", "success")
            return redirect(url_for('assets_list'))  # Redirige al listado de activos
        else:
            flash("Credenciales incorrectas. Inténtalo de nuevo.", "danger")
    return render_template('login.html')

# Endpoint de Logout
@app.route('/logout')
def logout():
    logout_user()
    flash("Has cerrado sesión.", "info")
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    return redirect(url_for('assets_list'))

# Ingreso de activos (incluye campo "observaciones")
@app.route('/assets', methods=['GET', 'POST'])
@login_required
@portfolio_required
def assets():
    if request.method == 'POST':
        # ——— Campos estáticos ———
        asset_name    = request.form.get('asset_name')
        location      = request.form.get('location')
        date_acquired = request.form.get('date_acquired')  # nuevo
        class_id      = request.form.get('class_id')
        subclass_id   = request.form.get('subclass_id')
        observaciones = request.form.get('observaciones', "")
        portfolio_id  = session.get('portfolio_id', 'default')

        # ——— Campos dinámicos ———
        month    = request.form.get('month')  # p.ej. "2025-04"
        try:
            amount = float(request.form.get('amount'))
        except (ValueError, TypeError):
            flash("El monto debe ser numérico.", "warning")
            return redirect(url_for('assets'))
        currency  = request.form.get('currency')
        status_id = request.form.get('status_id')

        conn = get_db_connection()
        try:
            # 1) Insertar en tabla assets (sólo datos estáticos)
            cursor = conn.execute(
                '''INSERT INTO assets
                   (name, location, date_acquired, class_id, subclass_id, portfolio_id, observations)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (asset_name, location, date_acquired, class_id, subclass_id, portfolio_id, observaciones)
            )
            asset_id = cursor.lastrowid

            # 2) Insertar en tabla asset_values (datos por mes)
            conn.execute(
                '''INSERT INTO asset_values
                   (asset_id, month, amount, currency, status_id)
                   VALUES (?, ?, ?, ?, ?)''',
                (asset_id, month, amount, currency, status_id)
            )

            conn.commit()
            flash("Activo creado exitosamente.", "success")
        except Exception as e:
            conn.rollback()
            flash("Error al insertar activo: " + str(e), "danger")
        finally:
            conn.close()

        return redirect(url_for('assets_list'))

    else:
        # GET: mostrar formulario. Necesitamos clases y estatus para los dropdowns
        conn = get_db_connection()
        classes  = conn.execute("SELECT * FROM classes").fetchall()
        statuses = conn.execute("SELECT * FROM statuses").fetchall()
        conn.close()
        return render_template('assets.html',
                               classes=classes,
                               statuses=statuses)

    
# Listado de activos
@app.route('/assets/list')
@login_required
@portfolio_required
def assets_list():
    # — 1) Determinar mes a mostrar (query param o mes actual) —
    month = request.args.get('month')
    if not month:
        month = datetime.now().strftime('%Y-%m')
    current_month = datetime.now().strftime("%Y-%m")

    portfolio_id = session.get('portfolio_id')
    conn = get_db_connection()
    # — 2) Traer assets con sus valores para ese mes —
    assets = conn.execute("""
        SELECT
          a.id,
          a.name           AS asset_name,
          a.location,
          a.date_acquired  AS fecha_ingreso,
          av.month,
          av.amount,
          av.currency,
          c.name           AS class_name,
          sc.name          AS subclass_name,
          s.name           AS status_name
        FROM assets a
        JOIN asset_values av  ON a.id = av.asset_id
        JOIN classes c       ON a.class_id = c.id
        JOIN subclasses sc   ON a.subclass_id = sc.id
        LEFT JOIN statuses s ON av.status_id = s.id
        WHERE av.month = ?
          AND a.portfolio_id = ?
        ORDER BY a.name
    """, (month, portfolio_id)).fetchall()

    # — 3) Generar lista de meses para el dropdown —
    months = conn.execute("""
        SELECT DISTINCT month
        FROM asset_values
        WHERE asset_id IN (
            SELECT id FROM assets WHERE portfolio_id = ?
        )
        ORDER BY month DESC
    """, (portfolio_id,)).fetchall()
    conn.close()

    # — 4) Renderizar exactamente con las variables que ya usas,
    #    pero agregando 'months' y 'selected_month' —
    current_month = datetime.now().strftime('%Y-%m')
    return render_template('assets_list.html',
                           assets=assets,
                           months=[m['month'] for m in months],
                           selected_month=month,
                           current_month=current_month)

# Actualizar activos del mes actual.
@app.route('/assets/update_current', methods=['GET', 'POST'])
@login_required
@portfolio_required
def update_current():
    current_month = datetime.now().strftime("%Y-%m")
    conn = get_db_connection()
    if request.method == 'POST':
        assets = conn.execute("SELECT id FROM assets WHERE month = ? AND portfolio_id = ?", (current_month, session.get('portfolio_id'))).fetchall()
        for asset in assets:
            new_amount = request.form.get(f"amount_{asset['id']}")
            if new_amount:
                try:
                    new_amount = float(new_amount)
                    conn.execute("UPDATE assets SET amount = ? WHERE id = ?", (new_amount, asset['id']))
                except ValueError:
                    pass
        conn.commit()
        conn.close()
        flash("Valores actualizados para el mes actual.", "success")
        return redirect(url_for('assets_list'))
    else:
        assets = conn.execute("SELECT * FROM assets WHERE month = ? AND portfolio_id = ? AND (observaciones IS NULL OR observaciones = '')",
                                (current_month, session.get('portfolio_id'))).fetchall()
        conn.close()
        return render_template('update_current.html', assets=assets, current_month=current_month)

# Edición de activo (incluye selección de clase, subclase y estatus)
@app.route('/assets/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@portfolio_required
def edit_asset(id):
    conn = get_db_connection()
    asset_row = conn.execute('SELECT * FROM assets WHERE id = ?', (id,)).fetchone()
    if asset_row is None:
        conn.close()
        flash("Activo no encontrado.", "danger")
        return redirect(url_for('assets_list'))

    if request.method == 'POST':
        # ——— Campos estáticos ———
        asset_name    = request.form.get('asset_name')
        location      = request.form.get('location')
        date_acquired = request.form.get('date_acquired')
        class_id      = request.form.get('class_id')
        subclass_id   = request.form.get('subclass_id')
        observaciones = request.form.get('observaciones', "")

        # ——— Campos dinámicos ———
        try:
            amount = float(request.form.get('amount'))
        except (ValueError, TypeError):
            flash("El monto debe ser numérico.", "warning")
            return redirect(url_for('edit_asset', id=id))
        currency  = request.form.get('currency')
        month     = request.form.get('month')       # p.ej. "2025-04"
        status_id = request.form.get('estado')      # debe ser el ID del status

        # 1) Actualizar tabla assets (sólo estáticos)
        conn.execute("""
            UPDATE assets
               SET name          = ?,
                   location      = ?,
                   date_acquired = ?,
                   class_id      = ?,
                   subclass_id   = ?,
                   observations  = ?
             WHERE id = ?
        """, (
            asset_name,
            location,
            date_acquired,
            class_id,
            subclass_id,
            observaciones,
            id
        ))

        # 2) Actualizar tabla asset_values (el registro de ese mes)
        conn.execute("""
            UPDATE asset_values
               SET amount    = ?,
                   currency  = ?,
                   status_id = ?
             WHERE asset_id = ?
               AND month    = ?
        """, (
            amount,
            currency,
            status_id,
            id,
            month
        ))

        conn.commit()
        conn.close()
        flash("Activo actualizado correctamente.", "success")
        return redirect(url_for('assets_list'))

    else:
        # —— Cargar datos dinámicos (último mes registrado) ——
        val = conn.execute("""
            SELECT month, amount, currency, status_id
              FROM asset_values
             WHERE asset_id = ?
             ORDER BY month DESC
             LIMIT 1
        """, (id,)).fetchone()

        # convertimos el row de assets a dict y mapeamos nombre
        asset = dict(asset_row)
        asset['asset_name']     = asset.get('name', "")
        asset['fecha_ingreso']  = asset.get('date_acquired', "")

        if val:
            asset['month']    = val['month']
            asset['amount']   = val['amount']
            asset['currency'] = val['currency']
            st = conn.execute("SELECT name FROM statuses WHERE id = ?", (val['status_id'],)).fetchone()
            asset['estado']   = st['name'] if st else ""
        else:
            asset['month']    = ""
            asset['amount']   = 0
            asset['currency'] = ""
            asset['estado']   = ""

        # ahora traemos los catálogos para los dropdowns
        classes    = conn.execute("SELECT * FROM classes").fetchall()
        subclasses = conn.execute("SELECT * FROM subclasses WHERE class_id = ?", (asset['class_id'],)).fetchall()
        statuses   = conn.execute("SELECT * FROM statuses").fetchall()
        conn.close()

        return render_template(
            'edit_asset.html',
            asset=asset,
            classes=classes,
            subclasses=subclasses,
            statuses=statuses
        )
        
# Eliminación de activo (con confirmación)
@app.route('/assets/delete/<int:id>', methods=['POST'])
@login_required
def delete_asset(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM assets WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    flash("Activo eliminado definitivamente.", "danger")
    return redirect(url_for('assets_list'))

# ------------------------------------------------------------------
# Copiar activos de un mes a otro con validación de selección
# ------------------------------------------------------------------
@app.route('/assets/copy', methods=['GET', 'POST'])
@login_required
@portfolio_required
def copy_assets():
    source_month = datetime.now().strftime("%Y-%m")
    default_new_month = source_month  
    current_portfolio_id = session.get('portfolio_id')

    conn = get_db_connection()
    if request.method == 'POST':
        new_month = request.form.get('new_month').strip()
        selected_assets = request.form.getlist('asset_ids')
        for asset_id in selected_assets:
            asset = conn.execute("SELECT * FROM assets WHERE id = ? AND portfolio_id = ?", (asset_id, current_portfolio_id)).fetchone()
            if asset:
                new_fecha = datetime.now().strftime("%Y-%m")
                conn.execute(
                    'INSERT INTO assets (asset_name, location, amount, currency, month, clase, observaciones, fecha_ingreso, portfolio_id, estado) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                    (asset['asset_name'], asset['location'], asset['amount'], asset['currency'], new_month, asset['clase'], asset['observaciones'], new_fecha, asset['portfolio_id'], asset['estado'])
                )
        conn.commit()
        conn.close()
        flash("Proceso de copia completado correctamente para el mes " + new_month, "success")
        return redirect(url_for('assets_list'))
    else:
        assets = conn.execute("""
            SELECT
                a.id,
                a.name             AS asset_name,
                a.location,
                av.amount          AS amount,
                av.currency        AS currency,
                c.name             AS clase,
                a.date_acquired    AS fecha_ingreso
            FROM asset_values av
            JOIN assets a   ON av.asset_id = a.id
            JOIN classes c  ON a.class_id = c.id
            WHERE av.month = ?
              AND a.portfolio_id = ?
            ORDER BY a.name
        """, (source_month, current_portfolio_id)).fetchall()
        conn.close()
        return render_template(
            'copy_assets.html',
            assets=assets,
            prev_month=source_month,
            default_new_month=default_new_month
        )

# Evolución de activos: Por mes y clase, normalizando a MXN.
@app.route('/assets/evolution')
@login_required
@portfolio_required
def assets_evolution():
    return redirect(url_for('assets_history_view'))
def assets_evolution():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM assets", conn)
    conn.close()
    if df.empty:
        chart_html = "<p>No hay datos para mostrar.</p>"
    else:
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
        df['clase'] = df['clase'].fillna('Unknown')
        df['valor_normalizado'] = df.apply(normalize_to_mxn, axis=1)
        df_grouped = df.groupby(['month', 'clase'])['valor_normalizado'].sum().reset_index()
        fig = px.bar(df_grouped, x='month', y='valor_normalizado', color='clase', barmode='group',
                     title="Evolución de Activos por Mes y Clase")
        total_value = df['valor_normalizado'].sum()
        fig.update_layout(title=f"Evolución de Activos (Total: ${total_value:,.0f} MXN)",
                          yaxis=dict(tickformat=",.0f"))
        chart_html = fig.to_html(full_html=False)
    return render_template('assets_evolution.html', chart_html=chart_html)

# Crecimiento Mensual: Variación porcentual mes a mes (MXN).
@app.route('/assets/monthly_growth')
@login_required
def monthly_growth():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM assets", conn)
    conn.close()
    if df.empty:
        chart_html = "<p>No hay datos para mostrar.</p>"
    else:
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
        df['mxn_value'] = df.apply(normalize_to_mxn, axis=1)
        df_monthly = df.groupby('month')['mxn_value'].sum().reset_index()
        df_monthly = df_monthly.sort_values('month')
        df_monthly['growth'] = df_monthly['mxn_value'].pct_change() * 100
        fig = px.line(df_monthly, x='month', y='growth', markers=True, 
                      title="Crecimiento Porcentual Mensual (MXN)")
        fig.update_yaxes(tickformat=",.0f")
        chart_html = fig.to_html(full_html=False)
    return render_template('monthly_growth.html', chart_html=chart_html)

# Comparación de Exposición por Clase: Totales, porcentajes y desviación respecto a objetivos (MXN).
@app.route('/assets/class_comparison')
@login_required
def assets_class_comparison():
    config = load_config()
    target_exposure = config.get("target_exposure", {})
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM assets", conn)
    conn.close()
    if df.empty:
        return render_template('assets_class_comparison.html', comparison=[], total_portfolio=0)
    df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
    df['clase'] = df['clase'].fillna('Unknown')
    df['mxn_value'] = df.apply(normalize_to_mxn, axis=1)
    total_portfolio = df['mxn_value'].sum()
    df_grouped = df.groupby('clase')['mxn_value'].sum().reset_index()
    df_grouped['percentage'] = (df_grouped['mxn_value'] / total_portfolio) * 100
    comparison = []
    for _, row in df_grouped.iterrows():
        comparison.append({
            'clase': row['clase'],
            'value': row['mxn_value'],
            'percentage': row['percentage'],
            'target': target_exposure.get(row['clase'], None),
            'deviation': (row['percentage'] - target_exposure.get(row['clase'], 0)) if target_exposure.get(row['clase']) is not None else None
        })
    return render_template('assets_class_comparison.html', comparison=comparison, total_portfolio=total_portfolio)

# HISTÓRICO DE ACTIVOS: Tabla pivote con valores normalizados a USD (principal) y totales/variaciones en USD y MXN.
@app.route('/assets/history_view')
@login_required
def assets_history_view():
    # 1) Abrir conexión
    conn = get_db_connection()

    # 2) Traer histórico de valores
    sql = """
    SELECT
      a.id,
      a.name       AS asset_name,
      av.month     AS month,
      av.amount    AS amount,
      av.currency  AS currency
    FROM assets a
    JOIN asset_values av
      ON a.id = av.asset_id
    WHERE a.portfolio_id = ?
    ORDER BY av.month, a.name
    """
    df = pd.read_sql_query(sql, conn, params=(session.get('portfolio_id'),))
    conn.close()
   
    # 3) Si no hay datos
    if df.empty:
        table_html = "<p>No hay datos históricos para mostrar.</p>"
    else:
        # 4) Convertir amount y calcular valores USD/MXN
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
        df['usd_value'] = df.apply(lambda row: row['amount'] if row['currency'] == 'USD'
                                    else row['amount'] / get_exchange_rate(row['month']), axis=1)
        df['mxn_value'] = df.apply(lambda row: row['amount'] if row['currency'] == 'MXN'
                                    else row['amount'] * get_exchange_rate(row['month']), axis=1)
        months = sorted(df['month'].unique())
        exchange_rates = {m: get_exchange_rate(m) for m in months}
        totals_usd = {m: df[df['month']==m]['usd_value'].sum() for m in months}
        totals_mxn = {m: df[df['month']==m]['mxn_value'].sum() for m in months}

        # 5) Pivot y armado de tabla HTML (igual que antes)
        pivot = df.pivot_table(index='asset_name', columns='month', values='usd_value', aggfunc='sum').fillna("")
        html = "<table class='table table-bordered'>"
        # Header
        html += "<tr><th>Activo</th>" + "".join(f"<th>{m}</th>" for m in months) + "</tr>"
        # Tipo de cambio
        html += "<tr><th>TC</th>" + "".join(f"<th>{exchange_rates[m]}</th>" for m in months) + "</tr>"
        # Filas por activo
        for asset in pivot.index:
            html += "<tr><td>{}</td>{}</tr>".format(
                asset,
                "".join(f"<td>${pivot.loc[asset,m]:,.0f}</td>" if pivot.loc[asset,m]!="" else "<td></td>"
                        for m in months)
            )
        # Totales USD
        html += "<tr><td><strong>Total USD</strong></td>" + "".join(f"<td><strong>${totals_usd[m]:,.0f}</strong></td>" for m in months) + "</tr>"
        # Totales MXN
        html += "<tr><td><strong>Total MXN</strong></td>" + "".join(f"<td><strong>${totals_mxn[m]:,.0f}</strong></td>" for m in months) + "</tr>"
        # Variaciones (%)… (igual que antes)
        # … aquí iría tu lógica de variaciones sin cambios …

        html += "</table>"
        table_html = html

    return render_template('assets_history.html', table_html=table_html)

# Análisis AI: Sugerencias basadas en la distribución por clase.
@app.route('/assets/ai')
@login_required
def assets_ai():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM assets", conn)
    conn.close()
    config = load_config()
    threshold = config.get("risk_threshold", 60)
    if df.empty:
        suggestions = "No hay datos disponibles para el análisis."
    else:
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
        df['clase'] = df['clase'].fillna('Unknown')
        total_amount = df['amount'].sum()
        grouped = df.groupby('clase')['amount'].sum().reset_index()
        grouped['percentage'] = (grouped['amount'] / total_amount) * 100
        suggestions_list = []
        for index, row in grouped.iterrows():
            if row['percentage'] > threshold:
                suggestions_list.append(
                    f"Tu portafolio tiene {row['percentage']:.0f}% en la clase {row['clase']}. Considera reequilibrar tu cartera."
                )
        if not suggestions_list:
            suggestions_list.append("La distribución de tu portafolio se ve balanceada.")
        suggestions = "<br>".join(suggestions_list)
    return render_template('assets_ai.html', suggestions=suggestions)

# Configuración AI: Permite ajustar el umbral de riesgo y objetivos de exposición.
@app.route('/assets/ai/config', methods=['GET', 'POST'])
@login_required
def ai_config():
    config = load_config()
    message = None
    if request.method == 'POST':
        new_threshold = request.form.get('risk_threshold')
        try:
            new_threshold = int(new_threshold)
            config['risk_threshold'] = new_threshold
        except ValueError:
            message = "Por favor, ingresa un número válido para el umbral."
        target_exposure = {}
        for clase in ["Acciones", "Bonos", "Inmuebles", "Otros"]:
            value = request.form.get(clase)
            try:
                target_exposure[clase] = int(value)
            except (ValueError, TypeError):
                target_exposure[clase] = config.get("target_exposure", {}).get(clase, 0)
        config['target_exposure'] = target_exposure
        save_config(config)
        message = "Configuración actualizada correctamente."
    return render_template('ai_config.html', config=config, message=message)

# Tipo de Cambio Global: Permite actualizar el tipo de cambio para un mes.
@app.route('/exchange_rate', methods=['GET', 'POST'])
@login_required
def exchange_rate():
    if request.method == 'POST':
        month = request.form.get('month').strip()
        rate = request.form.get('rate')
        try:
            rate = float(rate)
        except ValueError:
            rate = 1
        conn = get_db_connection()
        existing = conn.execute('SELECT * FROM exchange_rate WHERE month = ?', (month,)).fetchone()
        if existing:
            conn.execute('UPDATE exchange_rate SET rate = ? WHERE month = ?', (rate, month))
        else:
            conn.execute('INSERT INTO exchange_rate (month, rate) VALUES (?, ?)', (month, rate))
        conn.commit()
        conn.close()
        return redirect(url_for('exchange_rate'))
    return render_template('exchange_rate.html')

# Help Page
@app.route('/help')
@login_required
def help_page():
    return render_template('help.html')

# ------------------------------------------------------------------
# ENDPOINTS PARA GESTIÓN DE PORTAFOLIOS
# ------------------------------------------------------------------
@app.route('/portfolios')
@login_required
def portfolios():
    conn = get_db_connection()
    portfolios = conn.execute('SELECT * FROM portfolios').fetchall()
    conn.close()
    return render_template('portfolios.html', portfolios=portfolios)

@app.route('/portfolios/create', methods=['GET', 'POST'])
@login_required
def create_portfolio():
    if request.method == 'POST':
        name = request.form.get('name')
        if name:
            conn = get_db_connection()
            try:
                conn.execute('INSERT INTO portfolios (name) VALUES (?)', (name,))
                conn.commit()
                flash("Portafolio creado exitosamente.", "success")
            except Exception as e:
                flash("Error al crear el portafolio: " + str(e), "danger")
            finally:
                conn.close()
            return redirect(url_for('portfolios'))
        else:
            flash("El nombre del portafolio es obligatorio.", "warning")
    return render_template('create_portfolio.html')

@app.route('/portfolios/select/<int:portfolio_id>')
@login_required
def select_portfolio(portfolio_id):
    session['portfolio_id'] = portfolio_id
    flash("Portafolio seleccionado.", "success")
    return redirect(url_for('assets_list'))

# ==================================================================
# CONTEXT PROCESSOR: Inyectar el nombre del portafolio actual en todas las plantillas
# ==================================================================
@app.context_processor
def inject_portfolio():
    portfolio_id = session.get('portfolio_id')
    name = "Default"
    conn = get_db_connection()
    row = conn.execute('SELECT name FROM portfolios WHERE id = ?', (portfolio_id,)).fetchone()
    conn.close()
    if row is not None:
        name = row['name']
    return {'current_portfolio_name': name}

import json
from flask import jsonify

# Endpoint para obtener las clases (Tipos de Activo)
@app.route('/api/classes')
def api_classes():
    conn = get_db_connection()
    classes = conn.execute("SELECT * FROM classes").fetchall()
    conn.close()
    # Convertir los resultados a lista de diccionarios
    classes_list = [dict(row) for row in classes]
    return jsonify(classes_list)

# Endpoint para obtener las subclases según una clase dada
@app.route('/api/subclasses/<int:class_id>')
def api_subclasses(class_id):
    conn = get_db_connection()
    subclasses = conn.execute("SELECT * FROM subclasses WHERE class_id = ?", (class_id,)).fetchall()
    conn.close()
    subclasses_list = [dict(row) for row in subclasses]
    return jsonify(subclasses_list)

# ==================================================================
# ENDPOINTS PARA CONFIGURACIÓN DE CATÁLOGOS
# ==================================================================

# Página principal del módulo de configuración de catálogos
@app.route('/config/catalogs')
@login_required
def config_catalogs():
    conn       = get_db_connection()
    classes    = conn.execute("SELECT * FROM classes").fetchall()
    subclasses = conn.execute("SELECT * FROM subclasses").fetchall()
    statuses   = conn.execute("SELECT * FROM statuses").fetchall()
    conn.close()
    return render_template(
        'config_catalogs.html',
        classes    = classes,
        subclasses = subclasses,
        statuses   = statuses
    )

# Configuración de Clases
@app.route('/config/clases', methods=['GET', 'POST'])
@login_required
def config_clases():
    conn = get_db_connection()
    if request.method == 'POST':
        name = request.form.get('name')
        if name:
            conn.execute("INSERT INTO classes (name) VALUES (?)", (name,))
            conn.commit()
            flash("Clase creada exitosamente.", "success")
        else:
            flash("El nombre de la clase es obligatorio.", "warning")
        conn.close()
        return redirect(url_for('config_clases'))
    else:
        classes = conn.execute("SELECT * FROM classes").fetchall()
        subclasses = conn.execute("SELECT * FROM subclasses").fetchall()
        conn.close()
        return render_template('config_clases.html', classes=classes)

# Editar una clase
@app.route('/config/clases/edit/<int:class_id>', methods=['GET', 'POST'])
@login_required
def edit_clase(class_id):
    conn = get_db_connection()
    clase = conn.execute("SELECT * FROM classes WHERE id = ?", (class_id,)).fetchone()
    if clase is None:
        conn.close()
        flash("Clase no encontrada.", "danger")
        return redirect(url_for('config_clases'))
    
    if request.method == 'POST':
        new_name = request.form.get('name')
        if not new_name:
            flash("El nombre no puede estar vacío.", "warning")
        else:
            conn.execute("UPDATE classes SET name = ? WHERE id = ?", (new_name, class_id))
            conn.commit()
            flash("Clase actualizada exitosamente.", "success")
        conn.close()
        return redirect(url_for('config_clases'))
    conn.close()
    return render_template('edit_clase.html', clase=clase)

# Eliminar una clase
@app.route('/config/clases/delete/<int:class_id>', methods=['POST'])
@login_required
def delete_clase(class_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM classes WHERE id = ?", (class_id,))
    conn.commit()
    conn.close()
    flash("Clase eliminada.", "warning")
    return redirect(url_for('config_clases'))

# Configuración de Subclases
@app.route('/config/subclasses', methods=['GET', 'POST'])
@login_required
def config_subclasses():
    conn = get_db_connection()
    if request.method == 'POST':
        class_id = request.form.get('class_id')
        name = request.form.get('name')
        if class_id and name:
            conn.execute("INSERT INTO subclasses (class_id, name) VALUES (?, ?)", (class_id, name))
            conn.commit()
            flash("Subclase creada exitosamente.", "success")
        else:
            flash("Debe seleccionar una clase y escribir el nombre de la subclase.", "warning")
        conn.close()
        return redirect(url_for('config_subclasses'))
    else:
        # Para el formulario, se listan todas las clases
        classes = conn = get_db_connection()
        classes = conn.execute("SELECT * FROM classes").fetchall()
        subclasses = conn.execute("SELECT * FROM subclasses").fetchall()
        conn.close()
        return render_template('config_subclasses.html', classes=classes, subclasses=subclasses)

# Editar una subclase
@app.route('/config/subclasses/edit/<int:subclass_id>', methods=['GET', 'POST'])
@login_required
def edit_subclass(subclass_id):
    conn = get_db_connection()
    # 1. Carga la subclase a editar
    subclass = conn.execute("SELECT * FROM subclasses WHERE id = ?", (subclass_id,)).fetchone()
    if subclass is None:
        conn.close()
        flash("Subclase no encontrada.", "danger")
        return redirect(url_for('config_subclasses'))

    if request.method == 'POST':
        new_name = request.form.get('name')
        new_class_id = request.form.get('class_id')
        if not new_name or not new_class_id:
            flash("Todos los campos son obligatorios.", "warning")
        else:
            conn.execute(
                "UPDATE subclasses SET name = ?, class_id = ? WHERE id = ?",
                (new_name, new_class_id, subclass_id)
            )
            conn.commit()
            flash("Subclase actualizada exitosamente.", "success")
            conn.close()
            return redirect(url_for('config_subclasses'))
    
    # 2. Si es GET (o POST con error), necesitamos la lista de clases para el dropdown
    classes = conn.execute("SELECT * FROM classes").fetchall()
    conn.close()
    return render_template('edit_subclass.html', subclass=subclass, classes=classes)

# Eliminar una subclase
@app.route('/config/subclasses/delete/<int:subclass_id>', methods=['POST'])
@login_required
def delete_subclass(subclass_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM subclasses WHERE id = ?", (subclass_id,))
    conn.commit()
    conn.close()
    flash("Subclase eliminada.", "warning")
    return redirect(url_for('config_subclasses'))


# Configuración de Estatus
@app.route('/config/statuses', methods=['GET', 'POST'])
@login_required
def config_statuses():
    conn = get_db_connection()
    if request.method == 'POST':
        name = request.form.get('name')
        if name:
            conn.execute("INSERT INTO statuses (name) VALUES (?)", (name,))
            conn.commit()
            flash("Estatus agregado exitosamente.", "success")
        else:
            flash("El nombre del estatus es obligatorio.", "warning")
        conn.close()
        return redirect(url_for('config_statuses'))
    else:
        statuses = conn.execute("SELECT * FROM statuses").fetchall()
        conn.close()
        return render_template('config_statuses.html', statuses=statuses)
    
    # Editar un estatus
@app.route('/config/statuses/edit/<int:status_id>', methods=['GET', 'POST'])
@login_required
def edit_status(status_id):
    conn = get_db_connection()
    status = conn.execute("SELECT * FROM statuses WHERE id = ?", (status_id,)).fetchone()
    if status is None:
        conn.close()
        flash("Estatus no encontrado.", "danger")
        return redirect(url_for('config_statuses'))
    
    if request.method == 'POST':
        new_name = request.form.get('name')
        if not new_name:
            flash("El nombre no puede estar vacío.", "warning")
        else:
            conn.execute("UPDATE statuses SET name = ? WHERE id = ?", (new_name, status_id))
            conn.commit()
            flash("Estatus actualizado exitosamente.", "success")
        conn.close()
        return redirect(url_for('config_statuses'))
    conn.close()
    return render_template('edit_status.html', status=status)

# Eliminar un estatus
@app.route('/config/statuses/delete/<int:status_id>', methods=['POST'])
@login_required
def delete_status(status_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM statuses WHERE id = ?", (status_id,))
    conn.commit()
    conn.close()
    flash("Estatus eliminado.", "warning")
    return redirect(url_for('config_statuses'))

@app.route('/assets/replicate/<start_month>/<end_month>', methods=['GET', 'POST'])
@login_required
@portfolio_required
def replicate_assets(start_month, end_month):
    # 1) Conexión y portafolio
    portfolio_id = session.get('portfolio_id')
    conn = get_db_connection()

    if request.method == 'POST':
        # 2) Construir lista de meses desde start_month hasta end_month
        try:
            current = datetime.strptime(start_month, "%Y-%m")
            end_dt  = datetime.strptime(end_month,   "%Y-%m")
        except ValueError:
            flash("Formato de mes inválido. Usa AAAA-MM.", "warning")
            conn.close()
            return redirect(url_for('assets_list'))

        months = []
        while current <= end_dt:
            months.append(current.strftime("%Y-%m"))
            current += relativedelta(months=1)

        # 3) Para cada mes (excepto el primero) y cada activo seleccionado, copiar valor
        selected_assets = request.form.getlist('asset_ids')
        for m in months[1:]:
            for asset_id in selected_assets:
                row = conn.execute("""
                    SELECT amount, currency, status_id
                    FROM asset_values
                    WHERE asset_id = ? AND month = ?
                """, (asset_id, start_month)).fetchone()

                if row:
                    conn.execute("""
                        INSERT OR IGNORE INTO asset_values
                          (asset_id, month, amount, currency, status_id)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        asset_id,
                        m,
                        row['amount'],
                        row['currency'],
                        row['status_id']
                    ))

        conn.commit()
        conn.close()

        flash(f"Activos replicados de {start_month} a {end_month}.", "success")
        return redirect(url_for('assets_list'))

    else:
        # 4) GET: leer los activos del mes origen con los campos que tu template espera
        base_assets = conn.execute("""
            SELECT
                a.id                  AS id,
                a.name                AS asset_name,
                a.location            AS location,
                av.amount             AS amount,
                av.currency           AS currency,
                av.status_id          AS status_id,
                c.name                AS clase,
                a.date_acquired       AS fecha_ingreso
            FROM asset_values av
            JOIN assets a   ON av.asset_id    = a.id
            LEFT JOIN classes c  ON a.class_id    = c.id
            WHERE av.month = ?
              AND a.portfolio_id = ?
            ORDER BY a.name
        """, (start_month, portfolio_id)).fetchall()

        conn.close()
        # 5) Renderizar la tabla de copia
        return render_template(
            'copy_assets.html',
            assets=base_assets,
            prev_month=start_month,
            default_new_month=end_month
        )
        
# ======================================================
# BLOQUE FINAL: Inicia la APLICACIÓN.
# ======================================================
if __name__ == '__main__':
    app.run(debug=True)