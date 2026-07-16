from datetime import datetime, timedelta
import calendar
# Добавили импорт save_limits для будущего исправления падения в UI
from src.database import load_transactions, load_limits, save_limits, append_transaction_to_file

class FinanceManager:
    def __init__(self):
        self.transactions = load_transactions()
        self.limits = load_limits()
        self._next_id = max([t["id"] for t in self.transactions], default=0) + 1

    def save_limit(self, category, limit_val):
        """Сохраняет лимит локально и записывает в файл."""
        self.limits[category] = limit_val
        save_limits(self.limits)

    def add_transaction(self, t_type, category, amount, date_str=None):
        """Добавляет транзакцию с нормализованной датой (полночь)."""
        if date_str:
            t_date = datetime.strptime(date_str, "%Y-%m-%d")
        else:
            # Нормализуем к полуночи, чтобы избежать временных сдвигов
            t_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        new_transaction = {
            "id": self._next_id,
            "type": t_type,
            "category": category,
            "amount": amount,
            "date": t_date  
        }
        
        self.transactions.append(new_transaction)
        self._next_id += 1
        
        append_transaction_to_file(new_transaction)

        if t_type == "расход" and category in self.limits:
            current_spent = self.get_monthly_spent_by_category(category, t_date)
            if current_spent > self.limits[category]:
                return True, {
                    "category": category,
                    "spent": current_spent,
                    "limit": self.limits[category]
                }
                
        return True, None

    def get_monthly_spent_by_category(self, category, base_date):
        """Считает траты по категории за календарный месяц указанной даты."""
        total = 0.0
        for t in self.transactions:
            if t["type"] == "расход" and t["category"] == category:
                if t["date"].year == base_date.year and t["date"].month == base_date.month:
                    total += t["amount"]
        return total

    def get_rolling_budget(self, days=30):
        """Расчет скользящего бюджета с нормализованными границами времени."""
        # Нормализуем текущую дату к полуночи
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        start_date = today - timedelta(days=days)
        
        income = 0.0
        expense = 0.0
        expense_days = set()
        
        for t in self.transactions:
            # Теперь сравнение абсолютно точное, транзакции первого дня окна не теряются
            if start_date <= t["date"] <= today:
                if t["type"] == "доход":
                    income += t["amount"]
                elif t["type"] == "расход":
                    expense += t["amount"]
                    expense_days.add(t["date"].date())
                    
        rolling_balance = income - expense
        total_active_days = len(expense_days)
        
        daily_avg_calendar = expense / days if days > 0 else 0.0
        daily_avg_active = expense / total_active_days if total_active_days > 0 else 0.0
            
        return rolling_balance, daily_avg_calendar, daily_avg_active, total_active_days
    
    def get_expenses_by_category(self, days=30, start_date_str=None, end_date_str=None):
        """Группирует расходы по категориям с защитой от временных искажений."""
        if start_date_str and end_date_str:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
        else:
            # Нормализуем дефолтные даты к полуночи
            end_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            start_date = end_date - timedelta(days=days)
        
        structure = {}
        for t in self.transactions:
            if t["type"] == "расход" and start_date <= t["date"] <= end_date:
                structure[t["category"]] = structure.get(t["category"], 0.0) + t["amount"]
                
        return structure

    def predict_end_of_month_balance(self):
            """
            Экстраполяция трат до конца текущего месяца на основе скользящего 30-дневного 
            окна с плавным линейным смещением в сторону метрик текущего месяца.
            """
            import calendar
            
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            _, num_days = calendar.monthrange(today.year, today.month)
            days_left = num_days - today.day
            
            total_balance = 0.0
            month_expenses = 0.0
            
            # Временное окно для расчета базовой скорости за последние 30 дней
            start_30_days = today - timedelta(days=30)
            expenses_30_days = 0.0
            
            for t in self.transactions:
                amt = t["amount"]
                
                # Глобальный баланс (Доходы - Расходы)
                if t["type"] == "доход":
                    total_balance += amt
                elif t["type"] == "расход":
                    total_balance -= amt
                    
                    # Траты строго за текущий календарный месяц
                    if t["date"].year == today.year and t["date"].month == today.month:
                        month_expenses += amt
                    
                    # Траты за последние 30 дней от текущей даты
                    if start_30_days <= t["date"] <= today:
                        expenses_30_days += amt
                        
            days_passed = today.day
            
            # 1. Скорость трат в текущем месяце
            current_month_speed = month_expenses / days_passed if days_passed > 0 else 0.0
            
            # 2. Стабильная скорость за последние 30 дней
            rolling_30_speed = expenses_30_days / 30.0
            
            # 3. Расчет коэффициента смещения (от 0.0 в первый день до ~0.97 в последний)
            # На 1-й день месяца вес текущего месяца будет ровно 0.0 (прогноз 100% по rolling_30_speed)
            weight_current = (days_passed - 1) / num_days
            weight_rolling = 1.0 - weight_current
            
            # Итоговая интегральная скорость трат
            daily_expense_speed = (current_month_speed * weight_current) + (rolling_30_speed * weight_rolling)
            
            # Прогнозируем расходы до конца месяца и финальный остаток
            expected_future_expenses = daily_expense_speed * days_left
            predicted_balance = total_balance - expected_future_expenses
            
            return total_balance, predicted_balance, daily_expense_speed, expected_future_expenses