import asyncio
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)

# ====================== НАСТРОЙКИ ======================
BOT_TOKEN = "8497720886:AAHpilIlyrNChgH2c7B95DVMGYkIQbOnHWs"
ADMIN_IDS = [823985747]
GROUP_CHAT_ID = -5582366189
# =======================================================

# ---------- Хранилище в оперативной памяти ----------
settings = {
    "rate": 0.42,
    "min_amount": 10,
    "wallet": "TGFapPGxfC6E82vF87WGnfDrHuiZxW9yAc"
}

orders = {}
order_counter = 0
# ------------------------------------------------------

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

logging.basicConfig(level=logging.INFO)

# -------------------- Состояния FSM --------------------
class BuyStates(StatesGroup):
    custom_amount = State()
    trx_wallet = State()
    tx_hash = State()

class AdminStates(StatesGroup):
    rate = State()
    min_amount = State()
    wallet = State()
    broadcast = State()

# -------------------- Reply‑клавиатуры --------------------
def main_reply_keyboard():
    """Клавиатура под полем ввода — основные кнопки."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛒 Купить TRX")],
            [KeyboardButton(text="📋 Мои заказы"), KeyboardButton(text="ℹ️ Помощь")]
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие..."
    )

def cancel_reply_keyboard():
    """Клавиатура с кнопкой Отмена (для ввода данных)."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="↩️ Отмена")]],
        resize_keyboard=True,
        input_field_placeholder="Введите данные или отмените..."
    )

# -------------------- Инлайн‑клавиатуры (твои) --------------------
def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Купить TRX", callback_data="buy_trx")],
        [InlineKeyboardButton(text="📋 Мои заказы", callback_data="my_orders")],
        [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="help")]
    ])

def buy_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="30 TRX", callback_data="amt:30"),
         InlineKeyboardButton(text="50 TRX", callback_data="amt:50")],
        [InlineKeyboardButton(text="100 TRX", callback_data="amt:100"),
         InlineKeyboardButton(text="150 TRX", callback_data="amt:150")],
        [InlineKeyboardButton(text="🔢 Своя сумма", callback_data="custom_amount")],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="start")]
    ])

def payment_button(order_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"paid:{order_id}")],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="buy_trx")]
    ])

def admin_panel():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Текущие настройки", callback_data="admin_stats")],
        [InlineKeyboardButton(text="⚙️ Изменить настройки", callback_data="admin_settings")],
        [InlineKeyboardButton(text="📦 Неподтверждённые заказы", callback_data="admin_pending")],
        [InlineKeyboardButton(text="📨 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="⬅️ Закрыть", callback_data="close_admin")]
    ])

def settings_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💱 Курс TRX/USD", callback_data="set_rate")],
        [InlineKeyboardButton(text="💰 Мин. сумма (USD)", callback_data="set_min")],
        [InlineKeyboardButton(text="🏦 Кошелёк для оплаты", callback_data="set_wallet")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_menu")]
    ])

def confirm_order_btn(order_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm:{order_id}"),
         InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject:{order_id}")]
    ])

# -------------------- Утилиты --------------------
def new_order_id():
    global order_counter
    order_counter += 1
    return order_counter

async def notify_group(order):
    text = (
        "🔔 <b>Новый заказ TRX (подтверждён)</b>\n\n"
        f"👤 Пользователь: @{order['username']} ({order['first_name']})\n"
        f"🆔 ID: <code>{order['user_id']}</code>\n"
        f"💰 Сумма: <b>{order['amount_trx']} TRX</b> = <b>{order['price']:.2f} USD</b>\n"
        f"📅 Дата: {order['created_at']}\n"
        f"🏦 Кошелёк TRX (куда отправлять): <code>{order['trx_wallet']}</code>\n"
        f"🔗 Ссылка на транзакцию: <code>{order['tx_hash']}</code>\n"
        f"🧾 Номер заказа: <b>#{order['id']}</b>"
    )
    await bot.send_message(GROUP_CHAT_ID, text, parse_mode="HTML")

# -------------------- Обработчики команд --------------------
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    await message.answer(
        "💎 <b>SwillTRX</b> — покупка TRX, без AML проверок!\n"
        "💎 Все заявки обрабатываются вручную.\n"
        "🧾 Выберите действие:",
        reply_markup=main_reply_keyboard(),  # <-- Reply‑клавиатура
        parse_mode="HTML"
    )
    # Дополнительно отправляем инлайн‑меню (можно и без него, но оставим)
    await message.answer("Или используйте кнопки ниже:", reply_markup=main_menu())

@dp.message(Command("admin"))
async def admin_cmd(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return await message.answer("⛔ Доступ запрещён.")
    await message.answer("🔐 Админ‑панель", reply_markup=admin_panel(), parse_mode="HTML")

# -------------------- Обработка Reply‑кнопок --------------------
@dp.message(F.text == "🛒 Купить TRX")
async def reply_buy_trx(message: types.Message):
    # Имитируем нажатие инлайн‑кнопки
    rate = settings["rate"]
    min_am = settings["min_amount"]
    await message.answer(
        f"🛒 <b>Покупка TRX</b>\n\n"
        f"📈 Курс: 1 TRX = {rate:.4f} USD\n"
        f"🔻 Минимальная сумма: {min_am} USD\n\n"
        "Выберите количество TRX:",
        reply_markup=buy_menu(),
        parse_mode="HTML"
    )

@dp.message(F.text == "📋 Мои заказы")
async def reply_my_orders(message: types.Message):
    user_id = message.from_user.id
    user_orders = [o for o in orders.values() if o["user_id"] == user_id]
    if not user_orders:
        await message.answer("У вас пока нет заказов.", reply_markup=main_reply_keyboard())
        return
    lines = ["📋 <b>Ваши заказы:</b>\n"]
    for o in sorted(user_orders, key=lambda x: x["id"], reverse=True)[:5]:
        status_emoji = {"pending":"⏳","paid":"💰","confirmed":"✅"}.get(o["status"], "❓")
        lines.append(
            f"{status_emoji} <b>#{o['id']}</b> | {o['amount_trx']} TRX | {o['price']:.2f} USD\n"
            f"Статус: {o['status']}"
        )
    await message.answer("\n".join(lines), reply_markup=main_reply_keyboard(), parse_mode="HTML")

@dp.message(F.text == "ℹ️ Помощь")
async def reply_help(message: types.Message):
    await message.answer(
        "ℹ️ <b>Как купить TRX:</b>\n"
        "1️⃣ Выберите количество TRX\n"
        "2️⃣ Переведите USD (USDT) на указанный кошелёк\n"
        "3️⃣ Укажите ваш TRC20‑адрес для получения TRX и ссылку транзакции\n"
        "4️⃣ Оператор проверит платёж и <b>вручную</b> отправит вам TRX\n"
        "Время ожидания перевода до 15 минут.",
        reply_markup=main_reply_keyboard(),
        parse_mode="HTML"
    )

@dp.message(F.text == "↩️ Отмена")
async def cancel_action(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is not None:
        await state.clear()
        await message.answer("🚫 Действие отменено.", reply_markup=main_reply_keyboard())
        await message.answer("Главное меню:", reply_markup=main_menu())
    else:
        await message.answer("Вы не в процессе ввода.", reply_markup=main_reply_keyboard())

# -------------------- Callback: главное меню --------------------
@dp.callback_query(F.data == "start")
async def back_to_start(call: types.CallbackQuery):
    await call.message.edit_text(
        "💎 <b>SwillTRX</b> — покупка TRX вручную оператором.\n\n"
        "💎 Все заявки обрабатываются вручную\n"
        "🧾 Выберите действие:",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )
    # Обновим reply‑клавиатуру на всякий случай
    await call.message.answer("Главное меню:", reply_markup=main_reply_keyboard())

@dp.callback_query(F.data == "help")
async def help_info(call: types.CallbackQuery):
    await call.message.edit_text(
        "ℹ️ <b>Как купить TRX:</b>\n"
        "1️⃣ Выберите количество TRX\n"
        "2️⃣ Переведите USD (USDT) на указанный кошелёк\n"
        "3️⃣ Укажите ваш TRC20‑адрес для получения TRX и ссылку транзакции\n"
        "4️⃣ Оператор проверит платёж и <b>вручную</b> отправит вам TRX\n"
        "Время ожидания перевода до 15 минут.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="↩️ Назад", callback_data="start")]
        ]),
        parse_mode="HTML"
    )

# -------------------- Покупка TRX --------------------
@dp.callback_query(F.data == "buy_trx")
async def show_buy(call: types.CallbackQuery):
    rate = settings["rate"]
    min_am = settings["min_amount"]
    await call.message.edit_text(
        f"🛒 <b>Покупка TRX</b>\n\n"
        f"📈 Курс: 1 TRX = {rate:.4f} USD\n"
        f"🔻 Минимальная сумма: {min_am} USD\n\n"
        "Выберите количество TRX:",
        reply_markup=buy_menu(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("amt:"))
async def fixed_amount(call: types.CallbackQuery):
    amount = float(call.data.split(":")[1])
    await process_trx_amount(call, amount)

@dp.callback_query(F.data == "custom_amount")
async def ask_custom(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text("✏️ Введите желаемое количество TRX (только число):", parse_mode="HTML")
    # Показываем reply‑клавиатуру с Отменой
    await call.message.answer("Введите число или нажмите «Отмена»:", reply_markup=cancel_reply_keyboard())
    await state.set_state(BuyStates.custom_amount)

@dp.message(BuyStates.custom_amount)
async def custom_amount_input(message: types.Message, state: FSMContext):
    # Проверка на отмену уже сделана выше
    try:
        amount = float(message.text)
        if amount <= 0:
            raise ValueError
    except:
        await message.answer("❌ Введите положительное число.", reply_markup=cancel_reply_keyboard())
        return
    await state.clear()
    # Возвращаем основную reply‑клавиатуру
    await message.answer("Продолжаем...", reply_markup=main_reply_keyboard())
    await process_trx_amount(message, amount)

async def process_trx_amount(event, amount_trx):
    if isinstance(event, types.CallbackQuery):
        user = event.from_user
        msg = event.message
        edit = True
    else:
        user = event.from_user
        msg = event
        edit = False

    rate = settings["rate"]
    min_am = settings["min_amount"]
    price = round(amount_trx * rate, 2)

    if price < min_am:
        t = f"❌ Минимальная сумма покупки: {min_am} USD.\nВаша сумма: {price:.2f} USD."
        if edit:
            await msg.edit_text(t, reply_markup=buy_menu(), parse_mode="HTML")
        else:
            await msg.answer(t, reply_markup=buy_menu(), parse_mode="HTML")
        return

    wallet = settings["wallet"]
    oid = new_order_id()
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    orders[oid] = {
        "id": oid,
        "user_id": user.id,
        "username": user.username or "нет",
        "first_name": user.first_name,
        "amount_trx": amount_trx,
        "price": price,
        "wallet": wallet,
        "status": "pending",
        "created_at": now,
        "trx_wallet": "",
        "tx_hash": ""
    }

    text = (
        f"🛍 <b>Заказ #{oid}</b>\n\n"
        f"📌 Сумма: <b>{amount_trx} TRX</b>\n"
        f"💵 К оплате: <b>{price:.2f} USD</b>\n\n"
        f"🔹 Переведите точную сумму USDT (TRC20) на кошелёк:\n<code>{wallet}</code>\n\n"
        "После оплаты нажмите кнопку «Я оплатил»."
    )
    markup = payment_button(oid)
    if edit:
        await msg.edit_text(text, reply_markup=markup, parse_mode="HTML")
    else:
        await msg.answer(text, reply_markup=markup, parse_mode="HTML")

# -------------------- Оплата: ввод TRX-адреса и TX хеша --------------------
@dp.callback_query(F.data.startswith("paid:"))
async def paid_step(call: types.CallbackQuery, state: FSMContext):
    oid = int(call.data.split(":")[1])
    order = orders.get(oid)
    if not order:
        await call.answer("Заказ не найден.", show_alert=True)
        return
    await call.message.edit_text(
        "📥 Введите ваш <b>TRC20‑адрес</b>, на который вы хотите получить TRX.\n"
        "Формат: начинается с <code>T</code>, 34 символа.",
        parse_mode="HTML"
    )
    await call.message.answer("Введите адрес или нажмите «Отмена»:", reply_markup=cancel_reply_keyboard())
    await state.update_data(order_id=oid)
    await state.set_state(BuyStates.trx_wallet)

@dp.message(BuyStates.trx_wallet)
async def get_trx_wallet(message: types.Message, state: FSMContext):
    addr = message.text.strip()
    if not addr.startswith("T") or len(addr) != 34:
        await message.answer("❌ Некорректный адрес TRC20. Попробуйте ещё раз.", reply_markup=cancel_reply_keyboard())
        return
    data = await state.get_data()
    oid = data["order_id"]
    orders[oid]["trx_wallet"] = addr
    await state.update_data(order_id=oid)
    await message.answer(
        "🔗 Предоставьте ссылку на оплаченную транзакцию (Нажмите на транзакцию - Посмотреть в обозревателе блоков),\n\n"
        "В противном случае поставьте прочерк:",
        reply_markup=cancel_reply_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(BuyStates.tx_hash)

@dp.message(BuyStates.tx_hash)
async def get_tx_hash(message: types.Message, state: FSMContext):
    tx = message.text.strip()
    data = await state.get_data()
    oid = data["order_id"]
    order = orders.get(oid)
    if not order:
        await message.answer("Ошибка заказа.", parse_mode="HTML")
        await state.clear()
        return
    order["tx_hash"] = tx
    order["status"] = "paid"

    await message.answer(
        "✅ <b>Заказ оплачен!</b>\n"
        f"Номер заказа: #{oid}\n"
        "Ожидайте ручную проверку оператором. TRX будут отправлены на указанный вами адрес\n\n"
        "Если вы ошиблись с адресом, немедленно напишите в поддержку.",
        reply_markup=main_reply_keyboard(),  # возвращаем основную клавиатуру
        parse_mode="HTML"
    )
    await message.answer("Главное меню:", reply_markup=main_menu())
    await state.clear()

    # Уведомление админам
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"📥 Новый оплаченный заказ #{oid} от @{order['username']}\n"
                f"Сумма: {order['amount_trx']} TRX / {order['price']:.2f} USD\n"
                f"Адрес TRX: <code>{order['trx_wallet']}</code>\n"
                f"Ссылка на транзакцию: <code>{order['tx_hash']}</code>",
                reply_markup=confirm_order_btn(oid),
                parse_mode="HTML"
            )
        except:
            pass

# -------------------- Мои заказы (инлайн) --------------------
@dp.callback_query(F.data == "my_orders")
async def my_orders(call: types.CallbackQuery):
    user_id = call.from_user.id
    user_orders = [o for o in orders.values() if o["user_id"] == user_id]
    if not user_orders:
        await call.message.edit_text("У вас пока нет заказов.", reply_markup=main_menu(), parse_mode="HTML")
        return
    lines = ["📋 <b>Ваши заказы:</b>\n"]
    for o in sorted(user_orders, key=lambda x: x["id"], reverse=True)[:5]:
        status_emoji = {"pending":"⏳","paid":"💰","confirmed":"✅"}.get(o["status"], "❓")
        lines.append(
            f"{status_emoji} <b>#{o['id']}</b> | {o['amount_trx']} TRX | {o['price']:.2f} USD\n"
            f"Статус: {o['status']}"
        )
    await call.message.edit_text("\n".join(lines), reply_markup=main_menu(), parse_mode="HTML")

# -------------------- Админ‑панель (без изменений) --------------------
@dp.callback_query(F.data == "admin_menu")
async def back_admin(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return await call.answer("Нет доступа.")
    await call.message.edit_text("🔐 Админ‑панель", reply_markup=admin_panel(), parse_mode="HTML")

@dp.callback_query(F.data == "close_admin")
async def close_admin(call: types.CallbackQuery):
    await call.message.delete()

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return await call.answer("Нет доступа.")
    r, m, w = settings["rate"], settings["min_amount"], settings["wallet"]
    txt = (
        "📊 <b>Текущие настройки</b>\n\n"
        f"💱 Курс: 1 TRX = {r:.4f} USD\n"
        f"💰 Мин. сумма: {m} USD\n"
        f"🏦 Кошелёк для оплаты: <code>{w}</code>"
    )
    await call.message.edit_text(txt, reply_markup=settings_menu(), parse_mode="HTML")

@dp.callback_query(F.data == "admin_settings")
async def admin_settings_menu(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return await call.answer("Нет доступа.")
    await call.message.edit_text("⚙️ Выберите параметр для изменения:", reply_markup=settings_menu(), parse_mode="HTML")

@dp.callback_query(F.data == "set_rate")
async def set_rate(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return await call.answer("Нет доступа.")
    await call.message.edit_text("Введите новый курс TRX/USD (число, например 0.08):", parse_mode="HTML")
    await state.set_state(AdminStates.rate)

@dp.message(AdminStates.rate)
async def input_rate(message: types.Message, state: FSMContext):
    try:
        rate = float(message.text)
        if rate <= 0:
            raise ValueError
    except:
        await message.answer("❌ Введите положительное число.")
        return
    settings["rate"] = rate
    await state.clear()
    await message.answer(f"✅ Курс изменён: 1 TRX = {rate:.4f} USD", reply_markup=admin_panel(), parse_mode="HTML")

@dp.callback_query(F.data == "set_min")
async def set_min(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return await call.answer("Нет доступа.")
    await call.message.edit_text("Введите новую минимальную сумму в USD (число):", parse_mode="HTML")
    await state.set_state(AdminStates.min_amount)

@dp.message(AdminStates.min_amount)
async def input_min(message: types.Message, state: FSMContext):
    try:
        m = float(message.text)
        if m <= 0:
            raise ValueError
    except:
        await message.answer("❌ Введите положительное число.")
        return
    settings["min_amount"] = m
    await state.clear()
    await message.answer(f"✅ Мин. сумма: {m} USD", reply_markup=admin_panel(), parse_mode="HTML")

@dp.callback_query(F.data == "set_wallet")
async def set_wallet(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return await call.answer("Нет доступа.")
    await call.message.edit_text("Введите новый TRC20‑адрес для приёма USDT:", parse_mode="HTML")
    await state.set_state(AdminStates.wallet)

@dp.message(AdminStates.wallet)
async def input_wallet(message: types.Message, state: FSMContext):
    addr = message.text.strip()
    if not addr.startswith("T") or len(addr) != 34:
        await message.answer("❌ Некорректный адрес. Попробуйте ещё раз.")
        return
    settings["wallet"] = addr
    await state.clear()
    await message.answer(f"✅ Кошелёк обновлён: <code>{addr}</code>", reply_markup=admin_panel(), parse_mode="HTML")

@dp.callback_query(F.data == "admin_pending")
async def pending_orders(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return await call.answer("Нет доступа.")
    paid = [o for o in orders.values() if o["status"] == "paid"]
    if not paid:
        await call.message.edit_text("Нет заказов, ожидающих подтверждения.", reply_markup=admin_panel(), parse_mode="HTML")
        return
    for o in paid:
        text = (
            f"📦 <b>Заказ #{o['id']}</b>\n"
            f"👤 @{o['username']} ({o['first_name']})\n"
            f"💰 {o['amount_trx']} TRX = {o['price']:.2f} USD\n"
            f"🏦 TRX‑адрес: <code>{o['trx_wallet']}</code>\n"
            f"🔗 Link: <code>{o['tx_hash']}</code>\n"
            f"📅 {o['created_at']}"
        )
        await call.message.answer(text, reply_markup=confirm_order_btn(o["id"]), parse_mode="HTML")
    await call.message.answer("⬆️ Выше — заказы на подтверждение", reply_markup=admin_panel(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("confirm:"))
async def confirm_order(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return await call.answer("Нет доступа.")
    oid = int(call.data.split(":")[1])
    order = orders.get(oid)
    if not order or order["status"] != "paid":
        await call.answer("Заказ не найден или уже обработан.", show_alert=True)
        return
    order["status"] = "confirmed"
    await call.message.edit_text(f"✅ Заказ #{oid} подтверждён.", parse_mode="HTML")
    await notify_group(order)
    try:
        await bot.send_message(
            order["user_id"],
            f"✅ Ваш заказ #{oid} подтверждён! Оператор вручную отправит TRX на ваш адрес.",
            parse_mode="HTML"
        )
    except:
        pass

@dp.callback_query(F.data.startswith("reject:"))
async def reject_order(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return await call.answer("Нет доступа.")
    oid = int(call.data.split(":")[1])
    order = orders.get(oid)
    if not order or order["status"] != "paid":
        await call.answer("Заказ не найден или уже обработан.", show_alert=True)
        return
    order["status"] = "rejected"
    await call.message.edit_text(f"❌ Заказ #{oid} отклонён.", parse_mode="HTML")
    try:
        await bot.send_message(order["user_id"], f"❌ Ваш заказ #{oid} отклонён. Свяжитесь с поддержкой.", parse_mode="HTML")
    except:
        pass

# -------------------- Рассылка --------------------
@dp.callback_query(F.data == "admin_broadcast")
async def broadcast_prompt(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return await call.answer("Нет доступа.")
    await call.message.edit_text("📨 Введите текст для рассылки всем пользователям, у которых был хотя бы один заказ:", parse_mode="HTML")
    await state.set_state(AdminStates.broadcast)

@dp.message(AdminStates.broadcast)
async def do_broadcast(message: types.Message, state: FSMContext):
    users = {o["user_id"] for o in orders.values()}
    sent = 0
    for uid in users:
        try:
            await bot.send_message(uid, message.text, parse_mode="HTML")
            sent += 1
        except:
            pass
    await state.clear()
    await message.answer(f"📨 Рассылка завершена. Отправлено {sent} пользователям.", reply_markup=admin_panel(), parse_mode="HTML")

# -------------------- Запуск --------------------
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
