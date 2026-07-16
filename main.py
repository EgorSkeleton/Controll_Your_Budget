import calendar
import io
from contextlib import redirect_stdout
from datetime import datetime, timedelta
import urwid
import signal

from src.finance import FinanceManager
from src.utils import draw_ascii_chart, draw_limit_coverage_chart

# Инициализация менеджера финансов
manager = FinanceManager()

# Глобальный каркас приложения (Frame), в котором будет меняться содержимое (body)
frame = None

def capture_output(func, *args, **kwargs):
    """Вспомогательная функция для перехвата стандартного вывода (print) 
    из функций отрисовки графиков и преобразования его в строку для urwid."""
    f = io.StringIO()
    with redirect_stdout(f):
        func(*args, **kwargs)
    return f.getvalue()

def wrap_body(widgets):
    """Оборачивает список виджетов в общую палитру 'body' (черный текст, белый фон)."""
    pile = urwid.Pile(widgets)
    filler = urwid.Filler(pile, valign='top')
    return urwid.AttrMap(filler, 'body')

def show_main_menu(button=None, status_msg=""):
    """Отображение главного меню приложения."""
    body = [
        urwid.AttrMap(urwid.Text(" FINANCE MANAGEMENT SYSTEM v1.0.0 ", align="center"), 'header'),
        urwid.Divider(),
    ]
    if status_msg:
        body.append(urwid.Text(status_msg))
        body.append(urwid.Divider())

    menu_items = [
        ("1 - Add Transaction", lambda b: show_add_transaction()),
        ("2 - Set Category Limit", lambda b: show_set_limit()),
        ("3 - Show Transactions History", lambda b: show_history()),
        ("4 - View Rolling Budget", lambda b: show_rolling_budget()),
        ("5 - View End-of-Month Balance Forecast", lambda b: show_forecast()),
        ("6 - View Analytical Expense Diagrams", lambda b: show_diagrams()),
        ("0 - Exit Application", lambda b: raise_exit()),
    ]

    for label, callback in menu_items:
        btn = urwid.Button(label)
        urwid.connect_signal(btn, 'click', callback)
        body.append(urwid.AttrMap(btn, 'button', focus_map='focus'))

    frame.body = wrap_body(body)

def raise_exit(btn=None):
    """Выход из приложения."""
    raise urwid.ExitMainLoop()

def show_add_transaction():
    """Экран добавления транзакции."""
    date_edit = urwid.Edit("  Date (YYYY-MM-DD) [Leave empty for today]: ", datetime.now().strftime("%Y-%m-%d"))
    type_edit = urwid.Edit("  Type (доход/расход): ", "расход")
    cat_edit = urwid.Edit("  Category Name: ", "")
    amount_edit = urwid.Edit("  Amount (RUB): ", "")
    status_text = urwid.Text("")

    def submit(btn):
        d_str = date_edit.edit_text.strip()
        if not d_str:
            d_str = datetime.now().strftime("%Y-%m-%d")
        else:
            try:
                datetime.strptime(d_str, "%Y-%m-%d")
            except ValueError:
                status_text.set_text("[ERROR] Invalid date format. Use YYYY-MM-DD.")
                return

        t_type = type_edit.edit_text.strip().lower()
        if t_type not in ["доход", "расход"]:
            status_text.set_text("[ERROR] Invalid type. Use 'доход' or 'расход'.")
            return

        category = cat_edit.edit_text.strip().capitalize()
        if not category:
            status_text.set_text("[ERROR] Category cannot be empty.")
            return

        try:
            amount = float(amount_edit.edit_text.strip())
            if amount <= 0:
                status_text.set_text("[ERROR] Amount must be a positive number.")
                return
        except ValueError:
            status_text.set_text("[ERROR] Amount must be a valid number.")
            return

        success, alert = manager.add_transaction(t_type, category, amount, d_str)
        if success:
            msg = "[SUCCESS] Transaction logged successfully."
            if alert:
                msg += f"\nWARNING: Limit exceeded for '{alert['category']}'! Spent: {alert['spent']:.2f}, Limit: {alert['limit']:.2f}"
            status_text.set_text(msg)
        else:
            status_text.set_text("[ERROR] Failed to add transaction.")

    sub_btn = urwid.Button("Submit Transaction")
    urwid.connect_signal(sub_btn, 'click', submit)
    back_btn = urwid.Button("Back to Menu", lambda b: show_main_menu())

    widgets = [
        urwid.Text("NEW TRANSACTION", align="center"),
        urwid.Divider(),
        date_edit, type_edit, cat_edit, amount_edit,
        urwid.Divider(),
        urwid.AttrMap(sub_btn, 'button', focus_map='focus'),
        urwid.Divider(),
        status_text,
        urwid.Divider(),
        urwid.AttrMap(back_btn, 'button', focus_map='focus')
    ]
    frame.body = wrap_body(widgets)

def show_set_limit():
    """Экран установки лимита на категорию."""
    cat_edit = urwid.Edit("  Category Name: ", "")
    limit_edit = urwid.Edit("  Monthly Limit Amount (RUB): ", "")
    status_text = urwid.Text("")

    def submit(btn):
        category = cat_edit.edit_text.strip().capitalize()
        if not category:
            status_text.set_text("[ERROR] Category cannot be empty.")
            return
        try:
            limit_val = float(limit_edit.edit_text.strip())
            if limit_val < 0:
                status_text.set_text("[ERROR] Limit cannot be negative.")
                return
        except ValueError:
            status_text.set_text("[ERROR] Limit must be a valid number.")
            return

        manager.save_limit(category, limit_val)
        status_text.set_text(f"[SUCCESS] Monthly limit for '{category}' set to {limit_val:.2f} RUB.")

    sub_btn = urwid.Button("Save Limit")
    urwid.connect_signal(sub_btn, 'click', submit)
    back_btn = urwid.Button("Back to Menu", lambda b: show_main_menu())

    widgets = [
        urwid.Text("SET CATEGORY LIMIT", align="center"),
        urwid.Divider(),
        cat_edit, limit_edit,
        urwid.Divider(),
        urwid.AttrMap(sub_btn, 'button', focus_map='focus'),
        urwid.Divider(),
        status_text,
        urwid.Divider(),
        urwid.AttrMap(back_btn, 'button', focus_map='focus')
    ]
    frame.body = wrap_body(widgets)

def show_history():
    """Экран просмотра истории транзакций с фильтрами по типу, категории и датам."""
    type_edit = urwid.Edit("  Type Filter (доход / расход, leave empty for all): ", "")
    cat_edit = urwid.Edit("  Category Filter (leave empty for all): ", "")
    start_edit = urwid.Edit("  Start Date (YYYY-MM-DD, leave empty for all): ", "")
    end_edit = urwid.Edit("  End Date (YYYY-MM-DD, leave empty for all): ", "")

    fetch_btn = urwid.Button("Show History")
    back_btn = urwid.Button("Back to Menu", lambda b: show_main_menu())

    walker = urwid.SimpleFocusListWalker([])

    def update_list(content_widgets):
        walker[:] = [
            urwid.Text("TRANSACTION HISTORY", align="center"),
            urwid.Divider(),
            urwid.AttrMap(back_btn, 'button', focus_map='focus'),  # Кнопка возврата вверху
            urwid.Divider(),
            type_edit,
            cat_edit, 
            start_edit, 
            end_edit,
            urwid.Divider(),
            urwid.AttrMap(fetch_btn, 'button', focus_map='focus'),
            urwid.Divider(),
        ] + content_widgets

    def fetch_history(btn):
        target_type = type_edit.edit_text.strip().lower() or None
        target_category = cat_edit.edit_text.strip() or None
        start_input = start_edit.edit_text.strip()
        end_input = end_edit.edit_text.strip()

        start_date = None
        end_date = None

        if start_input:
            try:
                start_date = datetime.strptime(start_input, "%Y-%m-%d")
            except ValueError:
                update_list([urwid.Text("[ERROR] Invalid Start Date format. Use YYYY-MM-DD.")])
                return

        if end_input:
            try:
                end_date = datetime.strptime(end_input, "%Y-%m-%d")
            except ValueError:
                update_list([urwid.Text("[ERROR] Invalid End Date format. Use YYYY-MM-DD.")])
                return

        if start_date and end_date and end_date < start_date:
            update_list([urwid.Text("[ERROR] End date must be after start date.")])
            return

        type_title = f"TYPE: {target_type.upper()}" if target_type else "ALL TYPES"
        cat_title = f"CATEGORY: {target_category}" if target_category else "ALL CATEGORIES"
        date_range_title = f"{start_input or 'Beginning'} TO {end_input or 'Present'}"
        
        result_widgets = [
            urwid.Text(f"TRANSACTION LOG ({type_title} | {cat_title} | {date_range_title})"),
            urwid.Text("-" * 50)
        ]

        found = False
        counter = 1
        for t in manager.transactions:
            if target_type:
                t_type = t["type"].lower()
                if t_type != target_type:
                    continue

            if start_date and t["date"] < start_date:
                continue
            if end_date and t["date"] > end_date:
                continue
            if target_category and t["category"].lower() != target_category.lower():
                continue

            clean_date = t['date'].strftime("%Y-%m-%d")
            line_text = f"[{counter:03d}] {clean_date} | {t['type'].upper().ljust(7)} | {t['category'].ljust(15)} | {t['amount']:.2f} RUB"
            result_widgets.append(urwid.Text(line_text))
            counter += 1
            found = True

        if not found:
            result_widgets.append(urwid.Text("No transactions found matching filters."))

        update_list(result_widgets)

    urwid.connect_signal(fetch_btn, 'click', fetch_history)
    update_list([urwid.Text("Enter filters above and click 'Show History'.")])
    
    # Оборачиваем ListBox в AttrMap 'body', чтобы список тоже был белым с черным текстом
    frame.body = urwid.AttrMap(urwid.ListBox(walker), 'body')

def show_rolling_budget():
    """Экран скользящего бюджета."""
    balance, avg_calendar, avg_active, active_days_count = manager.get_rolling_budget()
    lines = [
        "ROLLING BUDGET & INTENSITY ANALYSIS (30-DAY WINDOW)",
        "-" * 50,
        f"Total Period Balance: {balance:.2f} RUB",
        f"Active Days with Transactions: {active_days_count} / 30",
        "-" * 50,
        f"Calendar Daily Average (Burn Rate): {avg_calendar:.2f} RUB/day",
        f"Active Daily Average (Intensity): {avg_active:.2f} RUB/day"
    ]
    if 0 < active_days_count < 30:
        gap = 30 - active_days_count
        lines.append(f"Detected {gap} days without financial records.")
        lines.append(f"Operational load ({avg_active:.2f}) exceeds calendar budget ({avg_calendar:.2f}).")

    output_text = urwid.Text("\n".join(lines))
    back_btn = urwid.Button("Back to Menu", lambda b: show_main_menu())

    widgets = [
        urwid.Text("ROLLING BUDGET", align="center"),
        urwid.Divider(),
        output_text,
        urwid.Divider(),
        urwid.AttrMap(back_btn, 'button', focus_map='focus')
    ]
    frame.body = wrap_body(widgets)

def show_forecast():
    """Экран прогноза баланса на конец месяца."""
    try:
        total_balance, predicted_balance, speed, future_exp = manager.predict_end_of_month_balance()
        today = datetime.now()
        _, num_days = calendar.monthrange(today.year, today.month)
        days_left = num_days - today.day

        if predicted_balance < 0:
            status = "CRITICAL: DEFICIT DETECTED"
        elif predicted_balance < total_balance * 0.2:
            status = "WARNING: LOW RESIDUAL BALANCE"
        else:
            status = "STABLE / OPTIMAL"

        lines = [
            "FINANCIAL FORECAST: END OF CURRENT CALENDAR MONTH",
            "-" * 50,
            f"Current Total Balance: {total_balance:.2f} RUB",
            f"Использованная скорость трат: {speed:.2f} RUB/day",
            f"Expected Expenses (Next {days_left} days): {future_exp:.2f} RUB",
            "-" * 50,
            f"PREDICTED END-OF-MONTH BALANCE: {predicted_balance:.2f} RUB",
            f"STATUS: [{status}]"
        ]
        output_text = urwid.Text("\n".join(lines))
    except Exception as e:
        output_text = urwid.Text(f"[ERROR] Calculation failed: {e}")

    back_btn = urwid.Button("Back to Menu", lambda b: show_main_menu())
    widgets = [
        urwid.Text("BALANCE FORECAST", align="center"),
        urwid.Divider(),
        output_text,
        urwid.Divider(),
        urwid.AttrMap(back_btn, 'button', focus_map='focus')
    ]
    frame.body = wrap_body(widgets)

def show_diagrams():
    """Экран аналитических диаграмм с выбором режима и кастомного диапазона дат."""
    mode_group = []
    mode_rb1 = urwid.RadioButton(mode_group, "1 - Expense Structure (% of total expenses)", state=True)
    mode_rb2 = urwid.RadioButton(mode_group, "2 - Limit Coverage (% of category limits | Requires Window >= 30 Days)")

    time_group = []
    time_rb1 = urwid.RadioButton(time_group, "1 - Last 30 days (Rolling window)", state=True)
    time_rb2 = urwid.RadioButton(time_group, "2 - Custom date range (YYYY-MM-DD)")

    start_edit = urwid.Edit("  Start Date (YYYY-MM-DD): ", (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"))
    end_edit = urwid.Edit("  End Date (YYYY-MM-DD): ", datetime.now().strftime("%Y-%m-%d"))
    output_text = urwid.Text("")

    def generate_chart(btn):
        selected_mode = 1
        for rb in mode_group:
            if rb.state:
                if "Limit Coverage" in rb.get_label():
                    selected_mode = 2
                break

        selected_time = 1
        for rb in time_group:
            if rb.state:
                if "Custom" in rb.get_label():
                    selected_time = 2
                break

        expenses = {}
        window_title = ""
        delta_days = 30

        if selected_time == 1:
            expenses = manager.get_expenses_by_category(days=30)
            window_title = "30-DAY ROLLING WINDOW"
            delta_days = 30
        else:
            start_input = start_edit.edit_text.strip()
            end_input = end_edit.edit_text.strip()
            try:
                start_date = datetime.strptime(start_input, "%Y-%m-%d")
                end_date = datetime.strptime(end_input, "%Y-%m-%d")
                delta_days = (end_date - start_date).days + 1
                
                if delta_days <= 0:
                    output_text.set_text("[ERROR] End date must be chronologically after start date.")
                    return
                    
                expenses = manager.get_expenses_by_category(start_date_str=start_input, end_date_str=end_input)
                window_title = f"RANGE: {start_input} TO {end_input}"
            except ValueError:
                output_text.set_text("[ERROR] Invalid date format. Use YYYY-MM-DD.")
                return

        if selected_mode == 1:
            chart_str = capture_output(draw_ascii_chart, expenses)
            full_text = f"EXPENSE STRUCTURE DIAGRAM ({window_title})\n" + "-"*50 + "\n" + chart_str
            output_text.set_text(full_text)
        elif selected_mode == 2:
            if delta_days < 30:
                err_msg = (
                    f"[ERROR] Interval is too short ({delta_days} days).\n"
                    "        Budget variance analysis requires a macro period of >= 30 days\n"
                    "        due to the non-linear distribution of monthly expenses."
                )
                output_text.set_text(err_msg)
                return
            
            chart_str = capture_output(draw_limit_coverage_chart, expenses, manager.limits, delta_days=delta_days)
            full_text = f"LIMIT COVERAGE DIAGRAM ({window_title})\n" + "-"*50 + "\n" + chart_str
            output_text.set_text(full_text)

    gen_btn = urwid.Button("Generate Diagram")
    urwid.connect_signal(gen_btn, 'click', generate_chart)
    back_btn = urwid.Button("Back to Menu", lambda b: show_main_menu())

    widgets = [
        urwid.Text("SELECT ANALYSIS DIAGRAM MODE", align="center"),
        urwid.Divider(),
        mode_rb1, mode_rb2,
        urwid.Divider(),
        urwid.Text("SELECT TIME RANGE", align="center"),
        urwid.Divider(),
        time_rb1, time_rb2,
        start_edit, end_edit,
        urwid.Divider(),
        urwid.AttrMap(gen_btn, 'button', focus_map='focus'),
        urwid.Divider(),
        output_text,
        urwid.Divider(),
        urwid.AttrMap(back_btn, 'button', focus_map='focus')
    ]
    
    frame.body = urwid.AttrMap(urwid.ListBox(urwid.SimpleFocusListWalker([urwid.Pile(widgets)])), 'body')

# Палитра: белый фон, черный текст везде
palette = [
    ('body', 'black', 'white'),          
    ('header', 'black,bold', 'white'),   
    ('button', 'black', 'light gray'),   
    ('focus', 'white', 'black'),         
    ('error', 'dark red', 'white'),      
]

def main():
    global frame
    
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    
    initial_fill = urwid.AttrMap(urwid.SolidFill(' '), 'body')
    frame = urwid.Frame(initial_fill)
    
    show_main_menu()
    
    loop = urwid.MainLoop(frame, palette=palette)
    loop.run()

if __name__ == "__main__":
    main()