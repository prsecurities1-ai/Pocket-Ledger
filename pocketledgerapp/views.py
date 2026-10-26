from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from .forms import BudgetForm, CategoryForm, CurrencyPreferenceForm, SignUpForm, TransactionForm
from .models import Budget, Category, CurrencyPreference, Transaction


DEFAULT_CATEGORIES = {
    Category.Kind.EXPENSE: (
        "Food & dining",
        "Transport",
        "Shopping",
        "Bills & utilities",
        "Health",
        "Entertainment",
        "Home",
        "Other",
    ),
    Category.Kind.INCOME: ("Salary", "Freelance", "Investments", "Other income"),
}


def _ensure_default_categories(user):
    for kind, names in DEFAULT_CATEGORIES.items():
        Category.objects.bulk_create(
            [Category(user=user, kind=kind, name=name) for name in names],
            ignore_conflicts=True,
        )


def _currency_preference(user):
    preference, _ = CurrencyPreference.objects.get_or_create(user=user)
    return preference


def _dashboard_context(request, transaction_form=None, budget_form=None, category_form=None):
    today = timezone.localdate()
    currency_preference = _currency_preference(request.user)
    user_transactions = Transaction.objects.filter(user=request.user).select_related("category")

    search = request.GET.get("q", "").strip()[:100]
    kind = request.GET.get("kind", "")
    category_value = request.GET.get("category", "")
    start_text = request.GET.get("start", "")
    end_text = request.GET.get("end", "")
    date_filters_valid = True
    start_date = parse_date(start_text) if start_text else None
    end_date = parse_date(end_text) if end_text else None
    if (start_text and start_date is None) or (end_text and end_date is None):
        messages.error(request, "Enter valid start and end dates.")
        date_filters_valid = False
    if start_date and end_date and start_date > end_date:
        messages.error(request, "The start date must be before the end date.")
        date_filters_valid = False

    filtered = user_transactions
    if search:
        filtered = filtered.filter(
            Q(title__icontains=search)
            | Q(note__icontains=search)
            | Q(category__name__icontains=search)
        )
    if kind in Transaction.Kind.values:
        filtered = filtered.filter(kind=kind)
    if category_value.isdigit():
        filtered = filtered.filter(category_id=int(category_value))
    if date_filters_valid:
        if start_date:
            filtered = filtered.filter(date__gte=start_date)
        if end_date:
            filtered = filtered.filter(date__lte=end_date)

    page_obj = Paginator(filtered, 12).get_page(request.GET.get("page"))
    filtered_income = filtered.filter(kind=Transaction.Kind.INCOME).aggregate(total=Sum("amount"))[
        "total"
    ] or Decimal("0.00")
    filtered_expenses = filtered.filter(kind=Transaction.Kind.EXPENSE).aggregate(
        total=Sum("amount")
    )["total"] or Decimal("0.00")

    month_start = today.replace(day=1)
    monthly_transactions = user_transactions.filter(date__year=today.year, date__month=today.month)
    monthly_income = monthly_transactions.filter(kind=Transaction.Kind.INCOME).aggregate(
        total=Sum("amount")
    )["total"] or Decimal("0.00")
    monthly_expenses = monthly_transactions.filter(kind=Transaction.Kind.EXPENSE).aggregate(
        total=Sum("amount")
    )["total"] or Decimal("0.00")
    all_income = user_transactions.filter(kind=Transaction.Kind.INCOME).aggregate(
        total=Sum("amount")
    )["total"] or Decimal("0.00")
    all_expenses = user_transactions.filter(kind=Transaction.Kind.EXPENSE).aggregate(
        total=Sum("amount")
    )["total"] or Decimal("0.00")

    monthly_budgets = list(
        Budget.objects.filter(user=request.user, year=today.year, month=today.month).select_related(
            "category"
        )
    )
    overall_budget = next((item for item in monthly_budgets if item.category_id is None), None)
    total_budget = (
        overall_budget.amount
        if overall_budget
        else sum((item.amount for item in monthly_budgets), Decimal("0.00"))
    )
    expense_by_category = {
        row["category_id"]: row["total"]
        for row in monthly_transactions.filter(kind=Transaction.Kind.EXPENSE)
        .values("category_id")
        .annotate(total=Sum("amount"))
    }
    for budget in monthly_budgets:
        budget.spent = (
            monthly_expenses
            if budget.category_id is None
            else expense_by_category.get(budget.category_id, Decimal("0.00"))
        )
        budget.percent = (
            min(int(budget.spent / budget.amount * 100), 100) if budget.amount else 0
        )
    budget_progress = min(int(monthly_expenses / total_budget * 100), 100) if total_budget else 0

    chart_months = []
    chart_income = []
    chart_expenses = []
    for offset in range(5, -1, -1):
        month_index = today.month - offset
        year = today.year + (month_index - 1) // 12
        month = (month_index - 1) % 12 + 1
        chart_months.append(date(year, month, 1).strftime("%b"))
        month_data = user_transactions.filter(date__year=year, date__month=month)
        chart_income.append(float(month_data.filter(kind="income").aggregate(total=Sum("amount"))["total"] or 0))
        chart_expenses.append(float(month_data.filter(kind="expense").aggregate(total=Sum("amount"))["total"] or 0))
    category_spending = list(
        monthly_transactions.filter(kind=Transaction.Kind.EXPENSE)
        .values("category__name")
        .annotate(total=Sum("amount"))
        .order_by("-total")[:6]
    )

    return {
        "transaction_form": transaction_form or TransactionForm(user=request.user),
        "budget_form": budget_form or BudgetForm(user=request.user),
        "category_form": category_form or CategoryForm(),
        "transactions": page_obj,
        "page_obj": page_obj,
        "categories": Category.objects.filter(user=request.user),
        "income": filtered_income,
        "expenses": filtered_expenses,
        "filtered_balance": filtered_income - filtered_expenses,
        "balance": all_income - all_expenses,
        "monthly_income": monthly_income,
        "monthly_expenses": monthly_expenses,
        "monthly_balance": monthly_income - monthly_expenses,
        "month_start": month_start,
        "monthly_budgets": monthly_budgets,
        "total_budget": total_budget,
        "budget_progress": budget_progress,
        "search": search,
        "selected_kind": kind,
        "selected_category": category_value,
        "start_date": start_text,
        "end_date": end_text,
        "currency_preference": currency_preference,
        "currency_symbol": currency_preference.symbol,
        "chart_data": {
            "months": chart_months,
            "income": chart_income,
            "expenses": chart_expenses,
            "category_labels": [item["category__name"] for item in category_spending],
            "category_values": [float(item["total"]) for item in category_spending],
            "currency_symbol": currency_preference.symbol,
            "currency_code": currency_preference.currency,
        },
        "today": today,
    }


def index(request):
    if request.method == "POST" and not request.user.is_authenticated:
        action = request.POST.get("auth_action")
        if action == "register":
            form = SignUpForm(request.POST)
            if form.is_valid():
                user = form.save()
                _ensure_default_categories(user)
                login(request, user)
                messages.success(request, "Your account is ready. Welcome to PocketLedger!")
                return redirect("dashboard")
            return render(
                request,
                "pocketledgerapp/index.html",
                {"signup_form": form, "login_form": AuthenticationForm(request)},
            )
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            _ensure_default_categories(request.user)
            messages.success(request, "Welcome back!")
            return redirect("dashboard")
        return render(
            request,
            "pocketledgerapp/index.html",
            {"login_form": form, "signup_form": SignUpForm()},
        )
    if not request.user.is_authenticated:
        return render(
            request,
            "pocketledgerapp/index.html",
            {"login_form": AuthenticationForm(request), "signup_form": SignUpForm()},
        )

    _ensure_default_categories(request.user)
    context = _dashboard_context(request)
    context["login_form"] = AuthenticationForm(request)
    context["signup_form"] = SignUpForm()
    return render(request, "pocketledgerapp/index.html", context)


@require_POST
def logout_view(request):
    logout(request)
    messages.success(request, "You have been signed out.")
    return redirect("dashboard")


@login_required
@require_POST
def create_transaction(request):
    form = TransactionForm(request.POST, user=request.user)
    if form.is_valid():
        transaction = form.save(commit=False)
        transaction.user = request.user
        transaction.save()
        messages.success(request, "Transaction added.")
    else:
        messages.error(request, "Please check the transaction details: " + form.errors.as_text())
    return redirect("dashboard")


@login_required
@require_POST
def update_transaction(request, transaction_id):
    transaction = get_object_or_404(Transaction, pk=transaction_id, user=request.user)
    form = TransactionForm(request.POST, instance=transaction, user=request.user)
    if form.is_valid():
        form.save()
        messages.success(request, "Transaction updated.")
    else:
        messages.error(request, "Please check the transaction details: " + form.errors.as_text())
    return redirect("dashboard")


@login_required
@require_POST
def delete_transaction(request, transaction_id):
    transaction = get_object_or_404(Transaction, pk=transaction_id, user=request.user)
    transaction.delete()
    messages.success(request, "Transaction deleted.")
    return redirect("dashboard")


@login_required
@require_POST
def create_category(request):
    form = CategoryForm(request.POST, user=request.user)
    if form.is_valid():
        category = form.save(commit=False)
        category.user = request.user
        category.save()
        messages.success(request, f"{category.name} category created.")
    else:
        messages.error(request, "Please provide a valid category name and type.")
    return redirect("dashboard")


@login_required
@require_POST
def save_budget(request):
    form = BudgetForm(request.POST, user=request.user)
    if form.is_valid():
        values = form.cleaned_data
        matching = Budget.objects.filter(
            user=request.user,
            category=values["category"],
            year=values["year"],
            month=values["month"],
        )
        budget = matching.first()
        if budget:
            budget.amount = values["amount"]
            budget.save(update_fields=["amount", "updated_at"])
        else:
            budget = form.save(commit=False)
            budget.user = request.user
            budget.save()
        messages.success(request, "Monthly budget saved.")
    else:
        messages.error(request, "Please provide a valid budget amount, month, and category.")
    return redirect("dashboard")


@login_required
@require_POST
def update_currency(request):
    form = CurrencyPreferenceForm(request.POST)
    if form.is_valid():
        preference = _currency_preference(request.user)
        preference.currency = form.cleaned_data["currency"]
        preference.save(update_fields=["currency"])
        messages.success(request, f"Currency updated to {preference.get_currency_display()}.")
    else:
        messages.error(request, "Choose a supported currency.")
    return redirect("dashboard")
