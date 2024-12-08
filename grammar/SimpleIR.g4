grammar SimpleIR;

unit: function;

function: 'function' NAME localvars? params? statement* return;

localvars: 'localvars' NAME+;

params: 'params' NAME+;

return: 'return' operand=(NAME | NUM);

statement: assign | deref | ref | assignderef | operation | call | label | goto | ifgoto;

operation: NAME ':=' operand1=(NAME | NUM) operator=('+' | '-' | '*' | '/' | '%') operand2=(NAME | NUM);

assign: NAME ':=' operand=(NAME | NUM);

deref: NAME ':=' '*' NAME;

ref: NAME ':=' '&' NAME;

assignderef: '*' NAME ':=' operand=(NAME | NUM);

call: NAME ':=' 'call' NAME NAME*;

label: NAME ':';

goto: 'goto' NAME;

ifgoto: 'if' operand1=(NAME | NUM) operator=('=' | '!=' | '<' | '<=' | '>' | '>=') operand2=(NAME | NUM) 'goto' labelname=NAME;

NAME: [a-zA-Z_] ([a-zA-Z_] | [0-9])* ;
NUM: [0-9]+ ;

PLUS: '+' ;
MINUS: '-' ;
STAR: '*' ;
SLASH: '/' ;
PERCENT: '%' ;

EQ: '=' ;
NEQ: '!=' ;
LT: '<' ;
LTE: '<=' ;
GT: '>' ;
GTE: '>=' ;

WS:   [ \t\r\n]+ -> skip ;

COMMENT : '#' ~[\r\n]* -> skip ;
