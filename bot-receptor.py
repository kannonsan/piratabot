#!/usr/bin/env python3
import logging

import sys
from telegram import Updater, Emoji, ParseMode, TelegramError, Update
from telegram.dispatcher import run_async
import python3pickledb as pickledb
import traceback

# Configuration
BOTNAME = 'Recepção_Pirata'
TOKEN = '190680457:AAHuznj20qF2en21oPlcv3G52Sokn9c7mOo'

# Fill these if you want to use webhook
BASE_URL = 'example.com'  # Domain name of your server, without
# protocol. You may include a port, if you dont want to use 443.
HOST = '0.0.0.0'  # Public IP Address of your server
PORT = 5002  # Port on which the Webhook should listen on
CERT = 'cert.pem'
CERT_KEY = 'key.key'

help_text = 'Este bot recebe as pessoas que entram em um grupo ao qual ele ' \
            'pertence. Por padrão, apenas a pessoa que convidou o bot pode ' \
            'modificar suas configurações.\nCommands:\n\n' \
            '/boasvindas - Colocar mensagem de boas-vindas\n' \
            '/adeus - Colocar mensagem de despedida\n' \
            '/desativar\\_adeus - Desativar mensagem de despedida\n' \
            '/travar - Apenas a pessoa que convidou o bot pode mudar as mensagens\n'\
            '/destravar - Todas as pessoas podem mudar as mensagens\n\n' \
            'Você pode usar _$username_ e _$title_ como placeholders enquanto estabelece'\
            'as mensagens.\n' \

'''
Create database object
Database schema:
<chat_id> -> welcome message
<chat_id>_bye -> goodbye message
<chat_id>_adm -> user id of the user who invited the bot
<chat_id>_lck -> boolean if the bot is locked or unlocked
<chat_id>_quiet -> boolean if the bot is quieted

chats -> list of chat ids where the bot has received messages in.
'''
# Create database object
db = pickledb.load('bot.db', True)

if not db.get('chats'):
    db.set('chats', [])

# Set up logging
root = logging.getLogger()
root.setLevel(logging.DEBUG)

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

logger = logging.getLogger(__name__)


def checar(bot, update, override_lock=None):
    """
    Perform some checks on the update. If checks were successful, returns True,
    else sends an error message to the chat and returns False.
    """

    chat_id = update.message.chat_id
    chat_str = str(chat_id)

    if chat_id > 0:
        bot.sendMessage(chat_id=chat_id,
                        text='Por favor, adicione-me primeiro!')
        return False

    locked = override_lock if override_lock is not None \
        else db.get(chat_str + '_lck')

    if locked and db.get(chat_str + '_adm') != update.message.from_user.id:
        if not db.get(chat_str + '_quiet'):
            bot.sendMessage(chat_id=chat_id, text='Perdão, apenas a pessoa que me convidou'
                                                  'pode fazer isso.')
        return False

    return True


# Welcome a user to the chat
def ahoy(bot, update):
    """ Dá boas-vindas a uma pessoa nova no chat """

    message = update.message
    chat_id = message.chat.id
    logger.debug('%s joined to chat %d (%s)'
                 % (message.new_chat_participant.first_name,
                    chat_id,
                    message.chat.title))

    # Pull the custom message for this chat from the database
    text = db.get(str(chat_id))

    # Use default message if there's no custom one set
    if text is None:
        text = 'Olá, $username! Seja bem-vinda(o) a $title %s' \
                  % Emoji.GRINNING_FACE_WITH_SMILING_EYES

    # Replace placeholders and send message
    text = text.replace('$username',
                        message.new_chat_participant.first_name)\
        .replace('$title', message.chat.title)
    bot.sendMessage(chat_id=chat_id, text=text)


# Dá boas-vindas a alguém no chat
def adeus(bot, update):
    """ Envia mensagem de despedida para quem sai do chat """

    message = update.message
    chat_id = message.chat.id
    logger.debug('%s left chat %d (%s)'
                 % (message.left_chat_participant.first_name,
                    chat_id,
                    message.chat.title))

    # Pull the custom message for this chat from the database
    text = db.get(str(chat_id) + '_bye')

    # Despedida desativada
    if text is False:
        return

    # Usar mensagem padrão na falta de uma customizada
    if text is None:
        text = 'Adeus, $username!'

    # Replace placeholders and send message
    text = text.replace('$username',
                        message.left_chat_participant.first_name)\
        .replace('$title', message.chat.title)
    bot.sendMessage(chat_id=chat_id, text=text)


# Introduzir o bot a um chat onde ele tenha sido adicionado
def introduzir(bot, update):
    """
    Introduz o bot a um chat onde ele tenha sido adicionado e salva a ID de quem o convidou.
    """

    chat_id = update.message.chat.id
    invited = update.message.from_user.id

    logger.info('Convidado por %s para o chat %d (%s)'
                % (invited, chat_id, update.message.chat.title))

    db.set(str(chat_id) + '_adm', invited)
    db.set(str(chat_id) + '_lck', True)

    text = 'Olá, %s! Estarei recebendo quem entrar neste chat com uma' \
           ' mensagem simpática %s \nVeja o comando de /ajuda para mais detalhes!'\
           % (update.message.chat.title,
              Emoji.GRINNING_FACE_WITH_SMILING_EYES)
    bot.sendMessage(chat_id=chat_id, text=text)


# Mostrar texto de ajuda
def ajuda(bot, update):
    """ Mostra um texto de ajuda """

    chat_id = update.message.chat.id

    bot.sendMessage(chat_id=chat_id,
                    text=help_text,
                    parse_mode=ParseMode.MARKDOWN,
                    disable_web_page_preview=True)


# Colocar mensagem customizada
def set_ahoy(bot, update, args):
    """ Coloca uma mensagem customizada de boas-vindas """

    chat_id = update.message.chat.id

    # Checar contexto do grupo e privilégios de admin
    if not checar(bot, update):
        return

    # Split message into words and remove mentions of the bot
    message = ' '.join(args)

    # Continuar apenas se houver uma mensagem
    if not message:
        bot.sendMessage(chat_id=chat_id, text='You need to send a message,'
                                              ' too! For example:\n'
                                              '/welcome Hello $username,'
                                              ' welcome to $title!')
        return

    # Colocar mensagem no banco de dados
    db.set(str(chat_id), message)

    bot.sendMessage(chat_id=chat_id, text='Got it!')


# Colocar mensagem de despedida customizada
def set_adeus(bot, update, args):
    """ Habilita e coloca uma mensagem de despedida customizada """

    chat_id = update.message.chat.id

    # Check admin privilege and group context
    if not checar(bot, update):
        return

    # Split message into words and remove mentions of the bot
    message = ' '.join(args)

    # Only continue if there's a message
    if not message:
        bot.sendMessage(chat_id=chat_id, text='You need to send a message,'
                                              ' too! For example:\n'
                                              '/goodbye Goodbye, '
                                              '$username!')
        return

    # Put message into database
    db.set(str(chat_id) + '_bye', message)

    bot.sendMessage(chat_id=chat_id, text='Got it!')


def disable_goodbye(bot, update):
    """ Disables the goodbye message """

    chat_id = update.message.chat.id

    # Check admin privilege and group context
    if not check(bot, update):
        return

    # Disable goodbye message
    db.set(str(chat_id) + '_bye', False)

    bot.sendMessage(chat_id=chat_id, text='Got it!')


def lock(bot, update):
    """ Locks the chat, so only the invitee can change settings """

    chat_id = update.message.chat.id

    # Check admin privilege and group context
    if not check(bot, update, override_lock=True):
        return

    # Lock the bot for this chat
    db.set(str(chat_id) + '_lck', True)

    bot.sendMessage(chat_id=chat_id, text='Got it!')


def quiet(bot, update):
    """ Quiets the chat, so no error messages will be sent """

    chat_id = update.message.chat.id

    # Check admin privilege and group context
    if not check(bot, update, override_lock=True):
        return

    # Lock the bot for this chat
    db.set(str(chat_id) + '_quiet', True)

    bot.sendMessage(chat_id=chat_id, text='Got it!')


def unquiet(bot, update):
    """ Unquiets the chat """

    chat_id = update.message.chat.id

    # Check admin privilege and group context
    if not check(bot, update, override_lock=True):
        return

    # Lock the bot for this chat
    db.set(str(chat_id) + '_quiet', False)

    bot.sendMessage(chat_id=chat_id, text='Got it!')


def unlock(bot, update):
    """ Unlocks the chat, so everyone can change settings """

    chat_id = update.message.chat.id

    # Check admin privilege and group context
    if not check(bot, update):
        return

    # Unlock the bot for this chat
    db.set(str(chat_id) + '_lck', False)

    bot.sendMessage(chat_id=chat_id, text='Got it!')


def empty_message(bot, update):
    """
    Empty messages could be status messages, so we check them if there is a new
    group member, someone left the chat or if the bot has been added somewhere.
    """

    # Keep chatlist
    chats = db.get('chats')

    if update.message.chat.id not in chats:
        chats.append(update.message.chat.id)
        db.set('chats', chats)
        logger.info("I have been added to %d chats" % len(chats))

    if update.message.new_chat_participant is not None:
        # Bot was added to a group chat
        if update.message.new_chat_participant.username == BOTNAME:
            return introduce(bot, update)
        # Another user joined the chat
        else:
            return welcome(bot, update)

    # Someone left the chat
    elif update.message.left_chat_participant is not None:
        if update.message.left_chat_participant.username != BOTNAME:
            return goodbye(bot, update)


def broadcast(bot, update, args):
    """
    CLI command handler to send a broadcast message to all entries in the chat
    list. Used to send information about updates. Deleted or blocked chats will
    be deleted.
    """

    chats = db.get('chats')
    text = ' '.join(args)

    for chat_id in chats:
        print("Messaging chat %d" % chat_id)
        try:
            bot.sendMessage(chat_id=chat_id, text=text)
        except TelegramError as te:
            logger.warn(te)
            chats.remove(chat_id)
            logger.info("Removed chat_id %s from chat list." % chat_id)

        except:
            logger.warn("Error on chat_id %d:" % chat_id)
            traceback.print_exc()

    if len(chats) > 25:
        db.set('chats', chats)
        print("Broadcasted message!")
    else:
        print("Not deleted chat list - something seems to be wrong!")


def set_log_level(bot, update, args):
    """ Another CLI command. Changes the logging level for the console. """

    level = args[0]

    if level == "DEBUG":
        level = logging.DEBUG
    elif level == "INFO":
        level = logging.INFO
    elif level == "WARNING":
        level = logging.WARNING
    elif level == "ERROR":
        level = logging.ERROR
    else:
        logger.error("Unkown logging level.")
        return

    logging.basicConfig(level=level,
                        format='%(asctime)s - %(name)s - '
                               '%(levelname)s - %(message)s')
    logger.log(level, "Set logging level!")


def chatcount(bot, update):
    """ CLI command to print the amount of groups we're in """

    chats = db.get('chats')
    print("Added to %s groups." % len([chat for chat in chats if chat < 0]))


def error(bot, update, error, **kwargs):
    """ Error handling """

    try:
        if isinstance(error, TelegramError)\
                and error.message == "Unauthorized"\
                or "PEER_ID_INVALID" in error.message\
                and isinstance(update, Update):

            chats = db.get('chats')
            chats.remove(update.message.chat_id)
            db.set('chats', chats)
            logger.info('Removed chat_id %s from chat list'
                        % update.message.chat_id)
        else:
            logger.error("An error (%s) occurred: %s"
                         % (type(error), error.message))
    except:
        pass


def main():
    # Create the Updater and pass it your bot's token.
    updater = Updater(TOKEN, workers=2)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    dp.addTelegramCommandHandler("start", help)
    dp.addTelegramCommandHandler("help", help)
    dp.addTelegramCommandHandler('welcome', set_welcome)
    dp.addTelegramCommandHandler('goodbye', set_goodbye)
    dp.addTelegramCommandHandler('disable_goodbye', disable_goodbye)
    dp.addTelegramCommandHandler("lock", lock)
    dp.addTelegramCommandHandler("unlock", unlock)
    dp.addTelegramCommandHandler("quiet", quiet)
    dp.addTelegramCommandHandler("unquiet", unquiet)

    dp.addTelegramRegexHandler('^$', empty_message)

    dp.addStringCommandHandler('broadcast', broadcast)
    dp.addStringCommandHandler('level', set_log_level)
    dp.addStringCommandHandler('count', chatcount)

    dp.addErrorHandler(error)

    # Start the Bot and store the update Queue, so we can insert updates
    update_queue = updater.start_polling(poll_interval=1, timeout=5)

    '''
    # Alternatively, run with webhook:
    updater.bot.setWebhook(webhook_url='https://%s/%s' % (BASE_URL, TOKEN))

    # Or, if SSL is handled by a reverse proxy, the webhook URL is already set
    # and the reverse proxy is configured to deliver directly to port 6000:

    update_queue = updater.start_webhook(HOST, PORT, url_path=TOKEN)
    '''

    # Start CLI-Loop
    while True:
        text = input()

        # Gracefully stop the event handler
        if text == 'stop':
            updater.stop()
            break

        # else, put the text into the update queue
        elif len(text) > 0:
            update_queue.put(text)  # Put command into queue

if __name__ == '__main__':
    main()
