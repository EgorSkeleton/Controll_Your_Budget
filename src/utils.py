def draw_ascii_chart(data_dict):
    """Строит текстовую ASCII-диаграмму структуры расходов."""
    if not data_dict:
        print("Нет данных для отображения диаграммы.")
        return

    total = sum(data_dict.values())
    print("\n--- ТЕКСТОВАЯ ДИАГРАММА РАСХОДОВ ---")
    
    # Ищем самую длинную строку категории для красивого выравнивания
    max_len = max([len(cat) for cat in data_dict.keys()], default=10)
    
    for category, amount in data_dict.items():
        percentage = (amount / total) * 100 if total > 0 else 0
        bar_length = int(percentage / 5) 
        bar = "█" * bar_length + "░" * (20 - bar_length)
        
        print(f"{category.ljust(max_len)} [{bar}] {percentage:.1f}% ({amount:.2f} руб.)")
    print(f"------------------------------------\nВсего расходов: {total:.2f} руб.\n")

def draw_limit_coverage_chart(expenses_dict, limits_dict, delta_days):
    """
    Строит ASCII-диаграмму выполнения лимитов.
    Масштабирует лимит только для макро-периодов (>= 30 дней).
    """
    if not limits_dict:
        print("  [INFO] No limits defined in the system.")
        return

    months_factor = max(1.0, round(delta_days / 30.0, 1))

    print("\n" + "="*60)
    print(f" BUDGET LIMIT COVERSAGE DIAGRAM (PERIOD: ~{months_factor} MONTH(S))")
    print("-"*60)

    if not expenses_dict:
        print("  [INFO] No expenses recorded within this macro period.")
        print("-" * 60)
        return

    max_len = max([len(cat) for cat in limits_dict.keys()], default=10)

    for category, monthly_limit in limits_dict.items():
        if monthly_limit <= 0:
            continue

        # Масштабируем лимит под количество месяцев (минимум за 1 месяц)
        proportional_limit = monthly_limit * months_factor
        spent = expenses_dict.get(category, 0.0)

        percentage = (spent / proportional_limit) * 100 if proportional_limit > 0 else 0.0

        bar_length = min(int(percentage / 5), 20)
        bar = "█" * bar_length + "░" * (20 - bar_length)

        status_marker = " [CRITICAL: OVERLIMIT]" if percentage > 100 else ""

        print(f"  {category.ljust(max_len)} [{bar}] {percentage:5.1f}% ({spent:.2f} / {proportional_limit:.2f} RUB){status_marker}")