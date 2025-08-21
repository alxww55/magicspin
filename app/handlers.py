import asyncio
from aiogram import F, Router, html
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

import app.keyboards as kb
from app.cache.redis_logic import UserSession
from app.middleware import RateLimiter, RegisterUser

router = Router()
router.message.middleware(RateLimiter())
router.callback_query.middleware(RateLimiter())
router.callback_query.middleware(RegisterUser())
# router.callback_query.middleware(PushToDB())


class AuthorizationStatus(StatesGroup):
    unathorized = State()
    authorized = State()


@router.message(CommandStart())
async def handle_cmd_start(message: Message, state: FSMContext) -> None:
    user_session = UserSession(message.from_user.id)
    await user_session.init_instance()
    await state.update_data(user_session=user_session)
    if await state.get_state() == AuthorizationStatus.authorized:
        await message.answer("Already logged in", reply_markup=kb.main_menu_keyboard)
    else:
        await state.set_state(AuthorizationStatus.unathorized)
        keyboard, correct_emoji = await kb.create_captcha_keyboard(message.from_user.id)
        await message.answer(f"Hello, {message.from_user.first_name},\nwelcome to Magic Spin Slot Machine Simulator!\n\n[+] DEBUG login_attempts: {"%placeholder"}\nSolve a captcha to proceed\n\nClick on {correct_emoji} button below", reply_markup=keyboard)


@router.callback_query(F.data.startswith("captcha:"))
async def check_if_human(callback: CallbackQuery, state: FSMContext) -> None:
    _, chosen_emoji, correct, user_id = callback.data.split(":")
    user_session = UserSession(user_id)
    await user_session.init_instance()
    if chosen_emoji == correct:
        await state.set_state(AuthorizationStatus.authorized)
        await user_session.authorize_user()
        await user_session.get_coins_qty()
        await callback.answer(None)
        await callback.message.edit_text("You solved captcha! ✅")
        await callback.message.answer(f"🎰 {html.bold("Magic Spin - Slot machine simulator")}\n\n💸 Win combinations {html.bold("prizes:")}\n\n7️⃣7️⃣7️⃣ = Bid Amount x10\n\n⬜️⬜️⬜️ = Bid Amount x5\n\n🍋🍋🍋 = Bid Amount x2\n\n🍇🍇🍇 = Bid Amount x2\n\n{html.bold("This project is a non-commercial simulation of Telegram’s slot machine dice feature. It has been developed solely for educational and demonstration purposes.")}", parse_mode="html", reply_markup=kb.main_menu_keyboard)
    else:
        await callback.answer("False!")
        await callback.message.edit_text("Try again! ⛔")


@router.callback_query(F.data == "main:spin")
async def get_bid_amount(callback: CallbackQuery) -> None:
    await callback.answer(None)
    await callback.message.edit_text(f"Choose the Bid Amount from below:", reply_markup=kb.bid_amounts_keyboard)


@router.callback_query(F.data == "main:earn")
async def add_coins_from_main(callback: CallbackQuery) -> None:
    await callback.answer(None)
    await callback.message.edit_text(f"Choose amount for a top up from below:", reply_markup=kb.add_coins_keyboard)


@router.callback_query(F.data.startswith("bid_amount:"))
async def send_slotmachine(callback: CallbackQuery, state: FSMContext) -> None:
    amount = int(callback.data.split(":")[1])
    user_session = UserSession(callback.from_user.id)
    await user_session.init_instance()
    cached_coins = int(await user_session.get_coins_qty())
    await callback.answer(None)
    if cached_coins > 0 and cached_coins >= amount:
        await callback.message.edit_text(f"You chose {amount} 🪙", reply_markup=None)
        result = await callback.message.answer_dice(emoji="🎰")
        prizes = {64: 10, 43: 2, 22: 2, 1: 5}
        multiplier = prizes.get(result.dice.value, 0)

        if multiplier:
            win = amount * multiplier
            new_balance = cached_coins + win
            await user_session.change_coins_qty(new_balance)
            await asyncio.sleep(2.2)
            await callback.message.answer(f"💰 {html.bold("JACKPOT")} 💰\n\n{html.bold(f"YOU GOT: {win}")} 🪙\n\nYour balance: {new_balance}", parse_mode="html", reply_markup=kb.main_menu_keyboard)
        else:
            new_balance = cached_coins - amount
            await user_session.change_coins_qty(new_balance)
            await asyncio.sleep(2.2)
            await callback.message.answer(f"😟 {html.bold("Not this time! Try again and WIN!")}\n\nYour balance: {new_balance}\n\nTap Earn if you runned out of coins", parse_mode="html", reply_markup=kb.main_menu_keyboard)
    else:
        await callback.message.answer(f"😟 {html.bold("You ran out of coins!")} Add some: ", parse_mode=html, reply_markup=kb.add_coins_keyboard)


@router.callback_query(F.data.startswith("add_coins:"))
async def add_coins_from_spin(callback: CallbackQuery, state: FSMContext) -> None:
    amount = int(callback.data.split(":")[1])
    user_session = UserSession(callback.from_user.id)
    await user_session.init_instance()
    cached_coins = int(await user_session.get_coins_qty())
    await callback.answer(None)
    await user_session.change_coins_qty((cached_coins + amount))
    await callback.message.edit_text(f"Your balance is {cached_coins + amount} 🪙\n\nChoose an action from below:", reply_markup=kb.main_menu_keyboard)


@router.callback_query(F.data == "cancel")
async def go_to_main_from_bid_menu(callback: CallbackQuery):
    await callback.message.edit_text(f"🎰 {html.bold("Magic Spin - Slot machine simulator")}\n\n💸 You can win following {html.bold("prizes:")}\n\n7️⃣7️⃣7️⃣ = Bid Amount x10\n\n⬜️⬜️⬜️ = Bid Amount x5\n\n🍋🍋🍋 = Bid Amount x2\n\n🍇🍇🍇 = Bid Amount x2\n\nThis is just a simulator\n\n🎰 {html.bold("Spin now and WIN!")}", parse_mode="html", reply_markup=kb.main_menu_keyboard)
