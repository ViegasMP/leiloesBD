from configparser import ConfigParser
from random import random, randint
from flask import Flask, jsonify, request, session, render_template
from functools import wraps
from datetime import datetime, timedelta
import logging, psycopg2, time, jwt
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)
#para que o top 10 apareça na ordem certa
app.config['JSON_SORT_KEYS'] = False

'''
    Função que vai buscar a base de dados para que possa ser utilizada e se consiga interagir com ela
'''


def getdatabase(filename='DBConfig.ini', section='postgresql'):
    parser = ConfigParser()
    parser.read(filename)

    db = {}
    if parser.has_section(section):
        parametros = parser.items(section)
        for param in parametros:
            db[param[0]] = param[1]

    else:
        raise Exception('Section {0} not found in the {1} file'.format(section, filename))

    return db


app.config['SECRET_KEY'] = 'authentication'

'''
    Autenticação de utilizadores
'''


def check_token(func):
    @wraps(func)
    def wrapped(*args, **kwargs):
        token = request.args.get('token')
        if not token:
            return jsonify({'erro': 'Falta o token para autenticar o utilizador'})
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'])
        except (Exception) as error:
            print(error)
            return jsonify({'erro': 'Token inválido!'})
        return func(*args, **kwargs)

    return wrapped


@app.route('/user', methods=['PUT'])
def login():
    conn = None

    try:
        parametros = getdatabase()
        conn = psycopg2.connect(**parametros)
        cur = conn.cursor()

        username = request.form['username']
        password = request.form['password']

        cur.execute("Select * from pessoa where username='%s' and banido=FALSE" % (username))
        getLog = cur.fetchall()

        if (len(getLog) == 0):
            message = {"erro": "Não existe nenhum utilizador com esse username!"}
            return jsonify(message)
        if (getLog[0][2] != password):
            message = {"erro": "Palavra passe errada!"}
            return jsonify(message)

        session['logged_in'] = True
        authToken = jwt.encode({'userID': getLog[0][0], 'exp': datetime.now() + timedelta(seconds=3600)},
                               app.config['SECRET_KEY'])

        cur.close()
        conn.commit()
        return jsonify({"authToken": authToken.decode('utf-8')})

    except (Exception, psycopg2.DatabaseError) as error:
        message = {"Code": 409, "Error": "Ocorreu um erro na função!"}
        print(error)
        return jsonify(message)

    finally:
        if conn is not None:
            conn.close()
            print('End of request.\n')


'''
    Atualização Tempo Real
'''


def aps_test():
    conn = None
    try:
        parametros = getdatabase()
        conn = psycopg2.connect(**parametros)
        cur = conn.cursor()

        # buscar id de eleicoes que tenham acabado, sejam validas e ainda nao tenham vencedor declarado
        cur.execute(
            "Select id from leilao where DATE(fim) < CURRENT_TIMESTAMP and cancelado = FALSE and vencedor_id is null")
        getLeilao = cur.fetchall()
        # print(getLeilao[1][0])
        if (len(getLeilao) != 0):
            # buscar a licitação mais alta e o id da pessoa que a fez
            cur.execute(
                "Select max(valor), user_id from licitacao where leilao_id = %s and valido = TRUE group by user_id" %
                getLeilao[1][0])
            getVencedor = cur.fetchall()
            # print(getVencedor[0][1])

            # atualizar leilão com o id do vencedor
            cur.execute("UPDATE leilao SET vencedor_id = %s WHERE id =%s" % (getVencedor[0][1], getLeilao[1][0]))
            # calcular o id da mensagem
            while True:
                msg_id = randint(1000000000000, 9999999999999)
                cur.execute("Select * from mensagens_correio where msg_id=%s" % msg_id)
                test = cur.fetchall()
                if (len(test) == 0):
                    break

            # mandar mensagem ao vencedor
            cur.execute(
                "Insert into mensagens_correio(msg_id, titulo, horaentrega, mensagem, lida, horalida, leilao_id, user_id) values(%s, 'Parabens!', current_timestamp , 'voce ganhou um leilao!', FALSE, null, %s, %s)" % (
                    msg_id, getLeilao[1][0], getVencedor[0][1]))

        cur.execute(
            "Select distinct user_id from mensagens_correio where lida = FALSE")
        getMSG = cur.fetchall()
        if len(getMSG) != 0:
            for i in range(len(getMSG)):
                print("Nova Mensagem para o user %s!" % getMSG[i][0])

        cur.close()
        conn.commit()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)

    finally:
        if conn is not None:
            conn.close()


scheduler = BackgroundScheduler()
scheduler.add_job(func=aps_test, trigger='cron', second='*/30')
scheduler.start()

'''
    Regista user
'''


@app.route('/user', methods=['POST'])
def novoUser():
    conn = None

    try:
        parametros = getdatabase()
        conn = psycopg2.connect(**parametros)
        cur = conn.cursor()

        # vai buscar os valores inseridos no postman

        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        admin = request.form['admin']

        # teste e validação dos inputs
        cur.execute("Select username from pessoa where username='%s'" % (username))
        test = cur.fetchall()
        if (len(test) > 0):
            message = {"erro": "Este username já se encontra registado!"}
            return jsonify(message)

        cur.execute("Select email from pessoa where email='%s'" % (email))
        test = cur.fetchall()
        if (len(test) != 0):
            message = {"erro": "Este email já se encontra registado!"}
            return jsonify(message)

        while True:
            id = randint(1000000000000, 9999999999999)
            cur.execute("Select id from pessoa where id=%s" % (id))
            test = cur.fetchall()
            if (len(test) == 0):
                break

        cur.execute(
            "Insert into pessoa(id, username, password, email, admin, banido) values(%s, '%s', '%s', '%s', '%s', %s)" % (
                id, username, password, email, admin, False))

        cur.close()
        conn.commit()
        message = {"userId": id}
        return jsonify(message)

    except (Exception, psycopg2.DatabaseError) as error:
        message = {"Code": 409, "Error": "Ocorreu um erro na função!"}
        print(error)
        return jsonify(message)

    finally:
        if conn is not None:
            conn.close()
            print('End of request.\n')


'''
    Criar um novo leilão
'''


@app.route('/leilao/auth', methods=['POST'])
@check_token
def novoLeilao():
    conn = None

    try:
        parametros = getdatabase()
        conn = psycopg2.connect(**parametros)
        cur = conn.cursor()

        # vai buscar os valores inseridos no postman
        titulo = request.form['titulo']
        descricao = request.form['descricao']
        vendedor_code = request.args['token']
        vendedor = jwt.decode(vendedor_code, app.config['SECRET_KEY'])
        min_lic = request.form['min']
        fim = request.form['fim']
        artigo = request.form['artigo']

        # teste e validação dos inputs
        cur.execute("Select titulo from leilao where titulo='%s'" % (titulo))
        test = cur.fetchall()
        if (len(test) > 0):
            message = {"erro": "Já existe uma leilão com esse título!"}
            return jsonify(message)
        cur.execute("Select id from pessoa where banido = false and id=%s" % (vendedor['userID']))
        test = cur.fetchall()
        if (len(test) == 0):
            message = {"erro": "Não existe nenhum utilizador com esse ID!"}
            return jsonify(message)
        if (int(min_lic) <= 0):
            message = {"erro": "O valor mínimo tem que ser maior que 0!"}
            return jsonify(message)

        while True:
            id = randint(1000000000000, 9999999999999)
            cur.execute("Select id from leilao where id=%s" % (id))
            test = cur.fetchall()
            if len(test) == 0:
                break

        cur.execute(
            "Insert into leilao(titulo, descricao, id, vendedor_id, min, fim, artigo, cancelado) values('%s', '%s', %s, %s, %s, '%s', '%s', FALSE)" % (
                titulo, descricao, id, vendedor['userID'], min_lic, fim, artigo))

        cur.close()
        conn.commit()
        message = {"leilaoId": id}
        return jsonify(message)
    except (Exception, psycopg2.DatabaseError) as error:
        if isinstance(error, psycopg2.errors.UniqueViolation):
            message = {"Code": 409, "Error": "O leilão já existe!"}
        else:
            message = {"Code": 409, "Error": "Ocorreu um erro na função!"}
        print(error)
        return jsonify(message)

    finally:
        if conn is not None:
            conn.close()
            print('Database connection closed.')


'''
    Listar todos os leilões existentes
'''


@app.route('/leiloes', methods=['GET'])
def listarLeiloes():
    conn = None

    try:
        parametros = getdatabase()
        conn = psycopg2.connect(**parametros)
        cur = conn.cursor()

        cur.execute("Select * from leilao where fim > CURRENT_TIMESTAMP and cancelado = FALSE")
        getLeiloes = cur.fetchall()

        if len(getLeiloes) == 0:
            message = {"erro": "Não existem nenhum leilão registado na base de dados"}
            return jsonify(message)

        message = []
        for i in getLeiloes:
            dict = {"titulo": i[0], "leilaoId": i[3], "descricao": i[1]}
            message.append(dict)

        cur.close()
        conn.commit()
        return jsonify(message)

    except (Exception, psycopg2.DatabaseError) as error:
        message = {"Code": 409, "Error": "Ocorreu um erro na função!"}
        print(error)
        return jsonify(message)

    finally:
        if conn is not None:
            conn.close()
            print('End of request.\n')


'''
    Pesquisar por leilão ja existente 
'''


@app.route('/leiloes/<keyword>', methods=['GET'])
def pesquisarLeilaoExistente(keyword):
    conn = None

    try:
        parametros = getdatabase()
        conn = psycopg2.connect(**parametros)
        cur = conn.cursor()

        cur.execute(
            "Select * from leilao where cancelado = FALSE and CAST(leilao.id AS VARCHAR(30)) = %s or leilao.descricao=%s",
            (keyword, keyword))
        getLeiloes = cur.fetchall();

        if (len(getLeiloes) == 0):
            message = {"erro": "Não existem nenhum leilão registado na base de dados com o id ou com a descricao %s" % (
                keyword)}
            return jsonify(message)

        message = []
        for i in getLeiloes:
            dict = {"titulo": i[0], "leilaoId": i[3], "descricao": i[1]}
            message.append(dict)

        cur.close()
        conn.commit()
        return jsonify(message)

    except (Exception, psycopg2.DatabaseError) as error:
        message = {"Code": 409, "Error": "Ocorreu um erro na função!"}
        print(error)
        return jsonify(message)

    finally:
        if conn is not None:
            conn.close()
            print('End of request.\n')


'''
    Listar leilões em que o user tenha atividade
'''


@app.route('/leiloes/auth', methods=['GET'])
@check_token
def listarLeiloesAtividade():
    conn = None

    try:
        parametros = getdatabase()
        conn = psycopg2.connect(**parametros)
        cur = conn.cursor()

        user_code = request.args['token']
        user_code = jwt.decode(user_code, app.config['SECRET_KEY'])

        cur.execute("select * from licitacao where valido = TRUE and user_id = '%s'" % user_code['userID'])
        getUser = cur.fetchall()

        lista = []

        for i in range(len(getUser)):
            lista.append(getUser[i][2])

        cur.execute("select * from leilao where cancelado = false and vendedor_id = '%s'" % user_code['userID'])
        getUser = cur.fetchall()

        for i in range(len(getUser)):
            lista.append(getUser[i][3])

        message = []

        for j in range(len(lista)):
            cur.execute("select * from leilao where cancelado = false and id = '%s'" % lista[j])
            getList = cur.fetchall();
            dict = {"descricao": getList[0][1], "leilaoId": getList[0][3], "titulo": getList[0][0]}
            message.append(dict)

        cur.close()
        conn.commit()
        return jsonify(message)

    except (Exception, psycopg2.DatabaseError) as error:
        message = {"Code": 409, "Error": "Ocorreu um erro na função!"}
        print(error)
        return jsonify(message)

    finally:
        if conn is not None:
            conn.close()
            print('End of request.\n')


'''
    Consultar detalhes de um leilão
'''


@app.route('/leilao/<leilaoID>/', methods=['GET'])
def consultarLeilao(leilaoID):
    conn = None

    try:
        parametros = getdatabase()
        conn = psycopg2.connect(**parametros)
        cur = conn.cursor()

        cur.execute("Select * from leilao where cancelado = FALSE and id=%s" % (leilaoID))
        getLeilao = cur.fetchall();

        if (len(getLeilao) == 0):
            message = {"erro": "Não existem nenhum leilão registado na base de dados com o id %s" % (leilaoID)}
            return jsonify(message)

        message = {}
        message["titulo"] = getLeilao[0][0]
        message['leilaoID'] = getLeilao[0][3]
        message['descricao'] = getLeilao[0][1]
        message['termino'] = getLeilao[0][6]

        cur.execute("Select * from mural where leilao_id=%s" % (leilaoID))
        getMural = cur.fetchall();
        if (len(getMural) == 0):
            message['mural'] = "Ainda não foram adicionadas mensagens ao respetivo leilão!"
        else:
            aux = {}
            for i in getMural:
                user = 'user ' + str(i[3])
                aux[user] = i[2]
            message['mural'] = aux

        cur.execute("Select * from licitacao where valido = TRUE and leilao_id=%s" % (leilaoID))
        getLicitacao = cur.fetchall();
        if (len(getLicitacao) == 0):
            message['licitacao'] = "Ainda não foram efetuadas licitações no respetivo leilão!"
        else:
            aux = {}
            for i in getLicitacao:
                user = 'user ' + str(i[1])
                aux[user] = i[0]
            message['licitacao'] = aux

        cur.close()
        conn.commit()
        return jsonify(message)

    except (Exception, psycopg2.DatabaseError) as error:
        message = {"Code": 409, "Error": "Ocorreu um erro na função!"}
        print(error)
        return jsonify(message)

    finally:
        if conn is not None:
            conn.close()
            print('End of request.\n')


'''
   Licitar
'''


@app.route('/licitar/<leilaoID>/<licitacao>/auth', methods=['GET'])
@check_token
def licitar(leilaoID, licitacao):
    conn = None
    try:
        parametros = getdatabase()
        conn = psycopg2.connect(**parametros)
        cur = conn.cursor()

        # user_id a partir do token
        userid_code = request.args['token']
        userid = jwt.decode(userid_code, app.config['SECRET_KEY'])

        # ver se a pessoa do login não é banida
        cur.execute("Select * from pessoa where banido = FALSE and id=%s" % (userid['userID']))
        getPessoas = cur.fetchall()
        if len(getPessoas) == 0:
            message = {"erro": "Não há pessoas registada na base de dados com o id %s" % (userid['userID'])}
            return jsonify(message)

        # ver se o leilao passado não é cancelado
        cur.execute("Select * from leilao where cancelado = FALSE and id=%s" % leilaoID)
        getLeilao = cur.fetchall()
        if (len(getLeilao) == 0):
            message = {"erro": "Não existem nenhum leilão registado na base de dados com o id %s" % leilaoID}
            return jsonify(message)

        # guardar o valor da licitação mais alta mais alto até então e o user responsável por ela
        cur.execute("Select MAX(valor), user_id from licitacao where leilao_id=%s group by user_id" % leilaoID)
        getLicitacao = cur.fetchall()

        # id aleatorio para a nova licitação
        while True:
            num = randint(1, 9999999999999)
            cur.execute("Select numero from licitacao where numero=%s" % num)
            test = cur.fetchall()
            if len(test) == 0:
                break

        # leilao ainda ativo
        if getLeilao[0][6] > datetime.now():
            # licitação nova maior que a pre-existente
            if getLeilao[0][5] < int(licitacao):
                if len(getLicitacao) > 0 and getLicitacao[0][0] is not None and int(licitacao) < int(
                        getLicitacao[0][0]):
                    message = {"erro": "A licitação tem que ser superior ao valor mínimo de %s!" % licitacao}
                else:
                    # criar licitação
                    cur.execute(
                        "Insert into licitacao(valor, leilao_id, hora, valido, numero, user_id) values (%s, %s, CURRENT_TIMESTAMP, TRUE, %s, %s)" % (
                            str(licitacao), str(leilaoID), num, userid['userID']))

                    #notificar que uma licitação mais alta foi feita
                    if len(getLicitacao) > 0:
                        # calcular o id da mensagem
                        while True:
                            msg_id = randint(1, 9999999999999)
                            cur.execute("Select * from mensagens_correio where msg_id=%s" % msg_id)
                            test = cur.fetchall()
                            if (len(test) == 0):
                                break

                        # mandar mensagem ao que perdeu a posição de licitação mais alta
                        cur.execute(
                            "Insert into mensagens_correio(msg_id, titulo, horaentrega, mensagem, lida, horalida, leilao_id, user_id) values(%s, 'Atenção!', current_timestamp , 'alguem aumentou sua aposta!', FALSE, null, %s, %s)" % (
                                msg_id, str(leilaoID), getLicitacao[0][1]))
                    message = {"sucesso": "A licitação foi efetuada com sucesso"}
            else:
                message = {"erro": "A licitação tem que ser superior ao valor mínimo de %s!" % (licitacao)}
        else:
            message = {"erro": "O leilão já terminou!"}

        cur.close()
        conn.commit()
        return jsonify(message)

    except (Exception, psycopg2.DatabaseError) as error:
        message = {"Code": 409, "Error": "Ocorreu um erro na função!"}
        print(error)
        return jsonify(message)

    finally:
        if conn is not None:
            conn.close()
            print('End of request.\n')


'''
   Um administrador pode cancelar um leilão
'''


@app.route('/cancelaLeilao/<leilaoID>/auth', methods=['PATCH'])
@check_token
def cancelaLeilao(leilaoID):
    conn = None
    try:
        parametros = getdatabase()
        conn = psycopg2.connect(**parametros)
        cur = conn.cursor()

        # busca o token
        user_code = request.args['token']
        user = jwt.decode(user_code, app.config['SECRET_KEY'])

        # utilizador é admin
        cur.execute("Select * from pessoa where pessoa.id=%s and pessoa.admin= TRUE" % user['userID'])
        test = cur.fetchall()
        if (len(test) != 0):
            cur.execute("UPDATE leilao SET cancelado = TRUE WHERE id =%s" % leilaoID)
            message = {"Leilao_ID cancelado": leilaoID}
        else:
            message = {"não tem permissões de adminstrador": user['userID']}

        cur.close()
        conn.commit()
        return jsonify(message)

    except (Exception, psycopg2.DatabaseError) as error:
        message = {"Code": 409, "Error": "Ocorreu um erro na função!"}
        print(error)
        return jsonify(message)

    finally:
        if conn is not None:
            conn.close()
            print('Database connection closed.')


'''
   Um administrador pode banir um user
'''


@app.route('/banirUser/auth', methods=['PATCH'])
@check_token
# PATCH - Used to create new data or update/modify existing data at the specified resource
def banirUser():
    conn = None
    try:
        parametros = getdatabase()
        conn = psycopg2.connect(**parametros)
        cur = conn.cursor()

        # busca os valores inseridos no postman
        user_code = request.args['token']
        user_admin = jwt.decode(user_code, app.config['SECRET_KEY'])
        user_ban = request.form['user_ID']

        # pessoa não existe ou é outro administrador
        cur.execute("Select id from pessoa where pessoa.admin= FALSE and pessoa.id=%s" % user_ban)
        test = cur.fetchall()
        if (len(test) == 0):
            message = {"erro": "Não foi possível banir um utilizador com esse ID!"}
            return jsonify(message)

        # utilizador não é adm
        cur.execute("Select admin from pessoa where pessoa.id=%s and pessoa.admin= TRUE" % user_admin['userID'])
        test = cur.fetchall()
        if (len(test) == 0):
            message = {"erro": "Não existe nenhum administrador com esse ID!"}
        else:
            # marcar o user como banido e não deletá-lo da base de dados, assim impedimos que ele volte a se registar
            cur.execute("UPDATE pessoa SET banido = TRUE WHERE id =%s" % user_ban)
            # invalidar licitações de um user banido
            cur.execute("UPDATE licitacao SET valido = FALSE WHERE user_id=%s" % user_ban)
            # cancelar o leilao que pertence a um user banido
            cur.execute("UPDATE leilao SET cancelado = TRUE WHERE vendedor_id=%s" % user_ban)
            if (len(test) == 0):
                message = {"erro": "Não foi possível banir um utilizador com esse ID!"}
                return jsonify(message)
            message = {"Pessoa_ID banido": user_ban}

        cur.close()
        conn.commit()
        return jsonify(message)

    except (Exception, psycopg2.DatabaseError) as error:
        message = {"Code": 409, "Error": "Ocorreu um erro na função!"}
        print(error)
        return jsonify(message)

    finally:
        if conn is not None:
            conn.close()
            print('Database connection closed.')


'''
    Editar propriedades de um leilão
'''


@app.route('/leilao/<leilaoID>/auth', methods=['PUT'])
@check_token
def editLeilao(leilaoID):
    conn = None

    try:
        parametros = getdatabase()
        conn = psycopg2.connect(**parametros)
        cur = conn.cursor()

        vend_code = request.args['token']
        vend = jwt.decode(vend_code, app.config['SECRET_KEY'])

        cur.execute(
            "Select * from leilao where cancelado = FALSE id=%s and vendedor_id=%s" % (leilaoID, vend['userID']))
        getLeilao = cur.fetchall()

        if (len(getLeilao) == 0):
            message = {"erro": "Não existe nenhum leilão que satisfaça o pedido!"}
            return jsonify(message)

        titulo = request.form['titulo']
        titulo_bool = False
        if (len(titulo) > 0 and titulo != getLeilao[0][0]):
            titulo_bool = True
            cur.execute("Update leilao set titulo='%s' where id=%s" % (titulo, leilaoID))

        descricao = request.form['descricao']
        desc_bool = False
        if (len(descricao) > 0 and descricao != getLeilao[0][1]):
            desc_bool = True
            cur.execute("Update leilao set descricao='%s' where id=%s" % (descricao, leilaoID))

        cur.execute("Select * from leilao where id=%s and vendedor_id=%s" % (leilaoID, vend['userID']))
        getNew = cur.fetchall()

        if (titulo_bool is False and descricao is False):
            message = {"erro": "Não foram efetuadas quaisquer alterações no leilão!"}
            return jsonify(message)

        cur.execute(
            "Insert into historico(data_alteracao, titulo, descricao, leilao_id, bool_titulo, bool_desc) values (CURRENT_TIMESTAMP, '%s', '%s', %s, %s, %s)" % (
                getNew[0][0], getNew[0][1], leilaoID, titulo_bool, desc_bool))

        cur.close()
        conn.commit()
        return consultarLeilao(leilaoID)

    except (Exception, psycopg2.DatabaseError) as error:
        message = {"Code": 409, "Error": "Ocorreu um erro na função!"}
        print(error)
        return jsonify(message)

    finally:
        if conn is not None:
            conn.close()
            print('End of request.\n')


'''
    Escrever mensagem no mural de um leilao
'''


@app.route('/mural/<leilaoID>/auth', methods=['POST'])
@check_token
def addMsgMural(leilaoID):
    conn = None
    try:
        parametros = getdatabase()
        conn = psycopg2.connect(**parametros)
        cur = conn.cursor()

        # vai buscar os valores inseridos no postman
        userid_code = request.args['token']
        user = jwt.decode(userid_code, app.config['SECRET_KEY'])
        mensagem = request.form['mensagem']
        titulo = request.form['titulo']

        # validação dos inputs
        cur.execute("Select vendedor_id from leilao where cancelado = false and id='%s'" % leilaoID)
        getLeilao = cur.fetchall()

        # produz um ID unico random para a mensagem do mural
        while True:
            id = randint(1, 9999999999999)
            cur.execute("Select msg_id from mural where msg_id=%s" % id)
            test = cur.fetchall()
            if len(test) == 0:
                break

        # mensagem do mural nao pode ser vazia
        if (len(mensagem) <= 0):
            message = {"erro": "A mensagem tem que ter conteudo"}
            return jsonify(message)

        cur.execute(
            "Insert into mural(msg_id, titulo, mensagem, user_id, leilao_id, hora_post) values(%s, '%s', '%s', %s, %s, CURRENT_TIMESTAMP)" % (
                id, titulo, mensagem, user['userID'], leilaoID))

        # notificar o vendedor da mensagem no mural
        while True:
            msg_id = randint(1, 9999999999999)
            cur.execute("Select msg_id from mensagens_correio where msg_id=%s" % msg_id)
            test = cur.fetchall()
            if len(test) == 0:
                break
        # mandar mensagem ao vendedor
        cur.execute(
            "Insert into mensagens_correio(msg_id, titulo, horaentrega, mensagem, lida, horalida, leilao_id, user_id) values(%s, '%s', current_timestamp , '%s', FALSE, null, %s, %s)" % (
                msg_id, titulo, mensagem, leilaoID, getLeilao[0][0]))

        # notificar as outras pessoas interessadas do mural

        # id das pessoas do mural desse leilao
        cur.execute(
            "Select user_id from mural where leilao_id = '%s'" % leilaoID)
        getUsers = cur.fetchall()
        # print(getUsers[0][0])
        for user in getUsers:
            # produz um ID unico random para a mensagem privada
            while True:
                id_msg = randint(1, 9999999999999)
                cur.execute("Select msg_id from mensagens_correio where msg_id=%s" % id_msg)
                test = cur.fetchall()
                if len(test) == 0:
                    break

            # mandar mensagem ao user
            cur.execute(
                "Insert into mensagens_correio(msg_id, titulo, horaentrega, mensagem, lida, horalida, leilao_id, user_id) values(%s, '%s', current_timestamp , '%s', FALSE, null, %s, %s)" % (
                    id_msg, titulo, mensagem, leilaoID, user[0]))

        cur.close()
        conn.commit()
        message = {"msgID": id}
        return jsonify(message)

    except (Exception, psycopg2.DatabaseError) as error:
        if isinstance(error, psycopg2.errors.UniqueViolation):
            message = {"Code": 409, "Error": "mensagem repetida"}
        else:
            message = {"Code": 409, "Error": "Ocorreu um erro na função!"}
        print(error)
        return jsonify(message)

    finally:
        if conn is not None:
            conn.close()
            print('Database connection closed.')


'''
    Um administrador pode obter estatísticas de atividade na aplicação
'''


@app.route('/atividade/auth', methods=['GET'])
@check_token
def getEstatisticas():
    conn = None
    try:
        parametros = getdatabase()
        conn = psycopg2.connect(**parametros)
        cur = conn.cursor()

        # busca o token login
        user_code = request.args['token']
        user = jwt.decode(user_code, app.config['SECRET_KEY'])

        # utilizador é admin
        cur.execute("Select * from pessoa where pessoa.id=%s and pessoa.admin= TRUE" % user['userID'])
        test = cur.fetchall()
        if (len(test) == 0):
            message = {"não tem permissões de adminstrador": user['userID']}
        else:
            # top 10 utilizadores com mais leilões criados
            cur.execute(
                "select distinct username, count(username) from pessoa, leilao where leilao.vendedor_id=pessoa.id group by username order by count(username) desc limit 10")
            top10vendedores = cur.fetchall()

            message = {}
            if (len(top10vendedores) == 0):
                message['top 10 vendedores'] = "Não existem um top 10"
            else:
                aux = {}
                for i in top10vendedores:
                    user = 'user ' + str(i[0])
                    aux[user] = i[1]
                message['top 10 vendedores'] = aux

            # top 10 utilizadores que mais leilões venceram
            cur.execute(
                "select distinct username, count(username) from pessoa, leilao where leilao.vencedor_id=pessoa.id group by username order by count(username) desc limit 10")
            top10vencedores = cur.fetchall()

            if (len(top10vencedores) == 0):
                message['top 10 vencedores'] = "Não existem um top 10"
            else:
                aux = {}
                for i in top10vencedores:
                    user = 'user ' + str(i[0])
                    aux[user] = i[1]
                print(aux)
                message['top 10 vencedores'] = aux

            # número total de leilões ativos nos últimos 10 dias
            cur.execute("select count(distinct titulo) from leilao where fim > current_date - interval '10 days'")
            leiloes10dias = cur.fetchall()
            if (len(leiloes10dias) == 0):
                message['leiloes ativos nos ultimos 10 dias'] = "Nenhum leilão ativo nos últimos 10 dias"
            else:
                message['leiloes ativos nos ultimos 10 dias'] = leiloes10dias[0][0]

        cur.close()
        conn.commit()
        return jsonify(message)

    except (Exception, psycopg2.DatabaseError) as error:
        if isinstance(error, psycopg2.errors.UniqueViolation):
            message = {"Code": 409, "Error": "mensagem repetida"}
        else:
            message = {"Code": 409, "Error": "Ocorreu um erro na função!"}
        print(error)
        return jsonify(message)

    finally:
        if conn is not None:
            conn.close()
            print('Database connection closed.')


'''
    Caixa de mensagem
'''


@app.route('/correio/auth', methods=['GET'])
@check_token
def lerMensagens():
    conn = None

    try:
        parametros = getdatabase()
        conn = psycopg2.connect(**parametros)
        cur = conn.cursor()

        user_code = request.args['token']
        user_code = jwt.decode(user_code, app.config['SECRET_KEY'])

        cur.execute("select * from mensagens_correio where user_id = '%s' order by horaentrega desc" % user_code['userID'])
        getMsg = cur.fetchall()
        message = []
        if len(getMsg)!= 0:
            print(getMsg)
            for i in range(len(getMsg)):
                dict = {"titulo": getMsg[i][1], "leilao": getMsg[i][6], "hora de entrega": getMsg[i][2], "mensasgem": getMsg[i][3]}
                message.append(dict)
                cur.execute("UPDATE mensagens_correio SET lida = TRUE and horalida = current_timestamp WHERE user_id =%s" % user_code['userID'])
        else:
            message.append("caixa de mensagens vazia")
        cur.close()
        conn.commit()
        return jsonify(message)

    except (Exception, psycopg2.DatabaseError) as error:
        message = {"Code": 409, "Error": "Ocorreu um erro na função!"}
        print(error)
        return jsonify(message)

    finally:
        if conn is not None:
            conn.close()
            print('End of request.\n')


