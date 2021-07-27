/*
	Caso as tabelas já existam de testes anteriores, apaga-as para que 
	a criação das novas tabelas com os dados iniciais seja bem sucedida
	e não haja problemas na base de dados
*/
drop table historico;
drop table licitacao;
drop table mural;
drop table leilao;
drop table mensagens_correio;
drop table pessoa;

/*
	Cria cada uma das tabelas com os respetivos atributos e respetivas 
	primary keys
*/
create table historico(
	data_alteracao 	timestamp,
	titulo 			text,
	descricao		text,
	leilao_id		bigint,
	bool_titulo		boolean,
	bool_desc		boolean
);

create table licitacao(
	valor		bigint,
	user_id 	bigint,
	leilao_id	bigint,
	hora		timestamp,
	valido		boolean,
	numero		bigint,
	primary key(numero)
);

create table mural(
	msg_id		bigint,
	titulo 		text,
	mensagem	text,
	user_id 	bigint,
	leilao_id 	bigint,
	hora_post 	timestamp,
	primary key(msg_id)
);

create table leilao(
	titulo 		text,
	descricao	text,
	vendedor_id	bigint,
	id 			bigint,
	vencedor_id bigint,
	min			bigint,
	fim			timestamp,
	artigo		text,
	cancelado	boolean,
	primary key(id)
);

create table mensagens_correio(
	msg_id		bigint,
	titulo 		text,
	horaentrega timestamp,
	mensagem	text,
	lida		boolean,
	horalida	timestamp,
	leilao_id	bigint,
	user_id		bigint,
	primary key(msg_id)
);

create table pessoa(
	id 			bigint,
	username	varchar(512),
	password	varchar(512),
	email		varchar(512),
	admin		boolean,
	banido		boolean,
	primary key(id)
);

/*
	Inserir dados nas tabelas para que estas não estejam vazias no arranque 
	do programa
*/
/* Pessoas */
insert into pessoa values(1234567890987, 'manuel', 'secret', 'manuel@gmail.pt', TRUE, FALSE);
insert into pessoa values(9876543212345, 'rmfonseca', 'pass', 'rita@uc.pt', FALSE, FALSE);	
insert into pessoa values(0192837465739, 'barbara', 'password', 'barbara@uc.pt', FALSE, FALSE);
insert into pessoa values(1231231231231, 'mariaPaula', 'palavraChave', 'mariaPaula@uc.pt', FALSE, FALSE);
insert into pessoa values(8768768768768, 'rui', 'nonono', 'ruinonono@gmail.pt', FALSE, TRUE);

/* Mensagens Correio */
insert into mensagens_correio values (8654, 'Atenção!', CURRENT_TIMESTAMP, 'alguem aumentou sua aposta!', FALSE, NULL, 9898989834343, 0192837465739);

/* Leilão */
insert into leilao values ('Máquina escrever', 'Máquina de escrever antiga que necessita de arranjo', 8768768768768, 4981237655679, NULL, 3025, NULL, 'Typewriter', TRUE);
insert into leilao values ('Desconfinar', 'Uma viagem de carro pela Europa com duração de 15 dias', 9876543212345, 9898989834343, NULL, 9000, NULL, 'Roadtrip', FALSE);

/* Mural */
insert into mural values (987654, 'Leilão cancelado', 'O leilão foi cancelado porque o artigo não se encontrava em condições', 1234567890987, 4981237655679, CURRENT_TIMESTAMP);

/* Licitações */
insert into licitacao values (10500, 1231231231231, 9898989834343, CURRENT_TIMESTAMP, TRUE, 183654281);
insert into licitacao values (9500, 0192837465739, 9898989834343, CURRENT_TIMESTAMP, TRUE, 976285652);


