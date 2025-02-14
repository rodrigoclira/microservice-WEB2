from django.shortcuts import redirect, render
from .utils import rand_N_digits, string_to_float
from .cruds import *
import requests
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from django.http.response import JsonResponse


MAX_TRIES = 10


def index(request):
    return render(request, 'web/index.html')


def login(request):
   
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        body = {"username": username, "password": password}

        api_response = requests.post("http://auth-api:8000/auth/login/", json=body)
        payload = api_response.json()

        if api_response.status_code == 200:
            request.session["jwt-access"] = payload["tokens"]["access"]
            request.session["jwt-refresh"] = payload["tokens"]["refresh"]
            request.session["user_id"] = payload["user_id"]
            response = redirect("/home")
        else:
            context = {"has_error": True, "error_message": payload["message"]}
            response = render(request, 'register/login.html', dict(context))

        return response

    return render(request, 'register/login.html',{})


def register_user(request):

    if request.method == "POST":
        full_name = request.POST.get("full_name")
        password = request.POST.get("password1")
        email = request.POST.get("email")
        cpf = request.POST.get("cpf")

        body = {"full_name": full_name, "password": password, "email": email, "cpf": cpf}

        register_response = create_user(body)

        if "has_error" not in register_response:
            request.session["user_id"] = register_response["id"]
            response = redirect("/register/account")
        else:
            response = render(request, 'register/register_user.html', dict(register_response))

        return response

    return render(request, 'register/register_user.html')


def register_account(request):

    if request.method == "POST":
        type_account = request.POST.get("type_account")
        try:
            owner_id = request.session["user_id"]
        except:
            context = {"has_error": "index", "error_message": "Sessão expirada"}
            return render(request, "error/erro.html", dict(context))
        
        balance = 0
        
        for i in range(MAX_TRIES):
            account_number = str(rand_N_digits(10))
            body = {
                "owner_id": owner_id,
                "account_number": account_number,
                "balance": balance,
                "type_account": type_account
                }
            
            account = create_account(body)

            if "has_error" not in account:
                account_id = account["id"]
                prefix_card_number = "3897 2468"
                password = request.POST.get("card_password")
                expire_date = str(date.today() + relativedelta(years=10))
                cvv = str(rand_N_digits(3))
                has_credit = True if type_account == "corrente" else False
                bill = 0
                limit = 1200

                for i in range(MAX_TRIES):
                    card_number_part1 = " " + str(rand_N_digits(4))
                    card_number_part2 = " " + str(rand_N_digits(4))
                    card_number = prefix_card_number + card_number_part1 + card_number_part2
                    body = {
                        "card_number": card_number,
                        "expire_date": expire_date,
                        "cvv": cvv,
                        "password": password,
                        "has_credit": has_credit,
                        "bill": bill,
                        "limit": limit,
                        "account": account_id
                        }
                    
                    card = create_card(body)

                    if "has_error" not in card:
                        return redirect('web:login')

                    elif i == MAX_TRIES - 1:
                        response_delete_account = delete_account(account_id)
                        response_delete_account["error_message"] = "Não foi possível criar a conta"
                        return render(request, 'register/register_account.html', dict(response_delete_account))
                        
                    else:
                        continue

            elif i == MAX_TRIES - 1:
                context = {"has_error": True, "error_message": "Não foi possível criar a conta"}
                return render(request, 'register/register_account.html', dict(context))

            else:
                continue
                
    return render(request,'register/register_account.html',{})


def home(request):
    
    if request.method == "GET":
        try:
            owner_id = request.session["user_id"]
        except:
            context = {"has_error": "index", "error_message": "Sessão expirada"}
            return render(request, "error/erro.html", dict(context))

        api_response_user = requests.get(f"http://auth-api:8000/auth/user/{owner_id}/")
        payload = api_response_user.json()

        if api_response_user.status_code == 200:
            account = get_account_from_owner(owner_id)

            if "has_error" in account:
                return render(request, "error/erro.html", dict(account))

            elif account == {}:
                return redirect("http://localhost/register/account")

            else:
                account_card = get_card_from_account(account["id"])

                transactions_account = get_transactions_from_account(account["id"])

                context = {"username": payload["full_name"], "account": account, "card": account_card, "transactions": list(reversed(transactions_account))}
                
                return render(request, 'web/home.html', dict(context))
        else:
            context = {"has_error": True, "error_message": payload["message"]}
            return render(request, "error/erro.html", dict(context))

    return render(request, "web/home.html")


def change_card_password(request):

    if request.method == "POST":
        try:
            owner_id = request.session["user_id"]
        except:
            return redirect("web:index")

        user_password = request.POST.get("user_password")
        card_password = request.POST.get("card_password")
        card_password2 = request.POST.get("card_password2")
        
        if card_password == card_password2:
            owner = get_user_by_id(owner_id)

            if "has_error" not in owner:
                
                if user_password == owner["password"]:

                    account = get_account_from_owner(owner_id)
                    
                    card = get_card_from_account(account["id"], convert=False)

                    if "has_error" not in card:
                        card["password"] = card_password
                        update_response = update_card(card)

                        if "has_error" not in update_response:
                            context = {"has_error": True, "error_message": "Senha do cartão atualizada!"}
                            return render(request, 'error/erro.html', dict(context))
                        else:
                            return render(request, 'error/erro.html', dict(update_response))

                    else:
                        return render(request, 'error/erro.html', dict(card))

                else:
                    context = {"has_error": True, "error_message": "Senha errada"}
                    return render(request, 'error/erro.html', dict(context))

            else:
                return render(request, 'error/erro.html', dict(owner))
            
        else:
            context = {"has_error": True, "error_message": "Senhas não foram digitadas iguais."}
            return render(request, 'error/erro.html', dict(context))

    return render(request,'web/changepassword.html',{})


def payment(request, account_id):

    if request.method == "POST":

        date_transaction = datetime.strftime(date.today(), '%Y-%m-%d')
        time_transaction = datetime.strftime(datetime.now(), "%H:%M:%S")
        payment_value = string_to_float(request.POST.get("payment_value"))
        type_transaction = "Pagamento"

        transaction_body = {
            "date": date_transaction,
            "time": time_transaction,
            "value": payment_value,
            "type_transaction": type_transaction,
            "account": account_id
            }
        
        account = get_account_by_id(account_id)

        if "has_error" not in account:
            balance = float(account["balance"])
            final_balance = round(balance - payment_value, 2)

            if final_balance < 0:
                context = {"has_error": True, "error_message": "Saldo Insuficiente"}
                return render(request, 'error/erro.html', dict(context))
            else:
                card = get_card_from_account(account_id)
                final_bill = round(float(card["bill"]) - payment_value, 2)
                if card["bill"] == "0.00":
                    return redirect("web:home")
                    
                if final_bill < 0:
                    final_balance = round(final_balance + abs(final_bill), 2)
                    transaction_body["value"] = round(payment_value + final_bill, 2)
                    bill_update = update_card_bill(card["id"], 0)
                    
                    if "has_error" in bill_update:
                        return render(request, 'error/erro.html', dict(bill_update))

                else:
                    bill_update = update_card_bill(card["id"], final_bill)

                    if "has_error" in bill_update:
                        return render(request, 'error/erro.html', dict(bill_update))

                balance_update = update_account_balance(account_id, final_balance)
                        
                if "has_error" not in balance_update:
                    response_transaction = create_transaction(transaction_body)

                    if "has_error" not in response_transaction:
                        return redirect('web:home')
                    else:
                        return render(request, 'error/erro.html', dict(response_transaction))
                else:
                    return render(request, 'error/erro.html', dict(balance_update))
        
        else:
            return render(request, 'error/erro.html', dict(account))

    return redirect("web:home")


def deposit(request, account_id):

    if request.method == "POST":
        date_transaction = datetime.strftime(date.today(), '%Y-%m-%d')
        time_transaction = datetime.strftime(datetime.now(), "%H:%M:%S")
        deposit_value = string_to_float(request.POST.get("deposit_value"))
        type_transaction = "Depósito"

        transaction_body = {
            "date": date_transaction,
            "time": time_transaction,
            "value": deposit_value,
            "type_transaction": type_transaction,
            "account": account_id
            }

        account = get_account_by_id(account_id)

        if "has_error" not in account:
            balance = float(account["balance"])
            final_balance = round(balance + deposit_value, 2)

            update_balance = update_account_balance(account_id, final_balance)
            
            if "has_error" not in update_balance:
                response_transaction = create_transaction(transaction_body)

                if "has_error" not in response_transaction:
                    return redirect('web:home')
                
                else:
                    return render(request, 'error/erro.html', dict(response_transaction))
            else:
                return render(request, 'error/erro.html', dict(update_balance))
        
        else:
            return render(request, 'web/home.html', dict(account))
    
    return redirect("web:home")


def transfer(request, account_id):

    if request.method == "POST":

        date_transaction = datetime.strftime(date.today(), '%Y-%m-%d')
        time_transaction = datetime.strftime(datetime.now(), "%H:%M:%S")
        transfer_value = string_to_float(request.POST.get("transfer_value"))
        account_transfer_number = request.POST.get("account_transfer_number")
        type_transaction = "Transferência"

        account = get_account_by_id(account_id)

        account_transfer = get_account_by_account_number(account_transfer_number)

        if ("has_error" not in account) and ("has_error" not in account_transfer):
            transaction_body = {
                "date": date_transaction,
                "time": time_transaction,
                "value": transfer_value,
                "type_transaction": type_transaction,
                "transfer_account": account_transfer["account_number"],
                "account": account_id
                }

            balance = float(account["balance"])
            final_balance = round(balance - transfer_value, 2)

            if final_balance < 0:
                context = {"has_error": True, "error_message": "Saldo Insuficiente"}
                return render(request, 'error/erro.html', dict(context))
            
            else:
                balance_transfer =  float(account_transfer["balance"])
                final_balance_transfer = round(balance_transfer + transfer_value, 2)
                
                update_balance = update_account_balance(account_id, final_balance)
                if "has_error" not in update_balance:
                    update_transfer_account_balance = update_account_balance(account_transfer["id"], final_balance_transfer)
                
                    if "has_error" not in update_transfer_account_balance:
                        response_transaction = create_transaction(transaction_body)

                        if "has_error" not in response_transaction:
                            return redirect('web:home')
    
                        else:
                            return render(request, 'error/erro.html', dict(response_transaction))
                    
                    else:
                        return render(request, 'error/erro.html', dict(update_transfer_account_balance))
                
                else:
                    return render(request, 'error/erro.html', dict(update_balance))

        elif "has_error" not in account:
            return render(request, 'error/erro.html', dict(account_transfer))
        else:
            return render(request, 'error/erro.html', dict(account))
    
    return redirect("web:home")


def buy(request, account_id):
    
    if request.method == "POST":
        payment_type = request.POST.get("payment_type")
        buy_value = string_to_float(request.POST.get("buy_value"))
        card_password = int(request.POST.get("card_password"))
        categories = request.POST.get("buy_type")
        date_transaction = datetime.strftime(date.today(), '%Y-%m-%d')
        time_transaction = datetime.strftime(datetime.now(), "%H:%M:%S")
        type_transaction = "Compra"

        account = get_account_by_id(account_id)

        if "has_error" not in account:
            
            card = get_card_from_account(account_id)

            if "has_error" not in card:

                if card_password == card["password"]:
                
                    if payment_type == "Débito":

                        transaction_body = {
                                "date": date_transaction,
                                "time": time_transaction,
                                "value": buy_value,
                                "categories": categories,
                                "type_transaction": type_transaction,
                                "payment_type": payment_type,
                                "account": account_id,
                                "card": card["id"]
                                }
                        
                        balance = float(account["balance"])
                        final_balance = round(balance - buy_value, 2)

                        if final_balance < 0:
                            context = {"has_error": True, "error_message": "Saldo Insuficiente"}
                            return render(request, 'error/erro.html', dict(context))
                        
                        else:
                            update_response = update_account_balance(account_id, final_balance)

                            if "has_error" not in update_response:
                                response_transaction = create_transaction(transaction_body)

                                if "has_error" not in response_transaction:
                                    return redirect('web:home')
                                else:
                                    return render(request, 'error/erro.html', dict(response_transaction))
                            
                            else:
                                return render(request, 'error/erro.html', dict(update_response))
                    
                    elif payment_type == "Crédito":

                            transaction_body = {
                                    "date": date_transaction,
                                    "time": time_transaction,
                                    "value": buy_value,
                                    "categories": categories,
                                    "type_transaction": type_transaction,
                                    "payment_type": payment_type,
                                    "account": account_id,
                                    "card": card["id"]
                                    }
                            
                            bill = float(card["bill"])
                            final_bill = round(bill + buy_value, 2)

                            if final_bill > float(card["limit"]):
                                context = {"has_error": True, "error_message": "Limite Insuficiente"}
                                return render(request, 'error/erro.html', dict(context))
                            
                            else:
                                update_response = update_card_bill(card["id"], final_bill)

                                if "has_error" not in update_response:
                                    response_transaction = create_transaction(transaction_body)

                                    if "has_error" not in response_transaction:
                                        return redirect('web:home')
                                    else:
                                        return render(request, 'error/erro.html', dict(response_transaction))
                                
                                else:
                                    return render(request, 'error/erro.html', dict(update_response))

                    else:
                        context = {"has_error": True, "error_message": "Opção de pagamento inválida"}
                        return render(request, 'error/erro.html', dict(context))

                else:
                    context = {"has_error": True, "error_message": "Senha do cartão incorreta"}
                    return render(request, 'error/erro.html', dict(context))
           
            else:
                return render(request, 'error/erro.html', dict(card))

    return redirect("web:home") 


def error(request):
    return render(request, 'error/erro.html')


def extrato(request):

    if request.method == "GET":
        try:
            owner_id = request.session["user_id"]
        except:
            context = {"has_error": "index", "error_message": "Sessão expirada"}
            return render(request, "error/erro.html", dict(context))

        account = get_account_from_owner(owner_id)

        if "has_error" not in account:
            transaction_id = request.GET.get("extrato")
            account_id = account["id"]

            if request.is_ajax():
                transaction = get_transaction_by_id(transaction_id, account_id)

                return JsonResponse(dict(transaction))
        
        else:
            return render(request, 'error/erro.html', dict(account))


def quit(request):
    request.session.flush()
    return redirect("web:index")


def delete(request):
    
    if request.method == "POST":
        try:
            owner_id = request.session["user_id"]
        except:
            context = {"has_error": "index", "error_message": "Sessão expirada"}
            return render(request, "error/erro.html", dict(context))

        password = request.POST.get("user_password")
        user = get_user_by_id(owner_id)

        if "has_error" not in user:
            account = get_account_from_owner(owner_id)
            
            if "has_error" not in account:
                
                if password == user["password"]:
                    delete_account(account["id"])
                    delete_user(owner_id)

                    context = {"has_error": "index", "error_message": "Conta deletada"}
                    return render(request, "error/erro.html", dict(context))
                
                else:
                    context = {"has_error": True, "error_message": "Senha errada"}
                    return render(request, 'error/erro.html', dict(context))
            
            else:
                return render(request, 'error/erro.html', dict(account))
        
        else:
            return render(request, 'error/erro.html', dict(user))
    
    return redirect("web:home")
