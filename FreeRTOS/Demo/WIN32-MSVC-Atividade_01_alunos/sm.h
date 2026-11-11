#ifndef SM_H
#define SM_H

//Criando a variavel prt apontando para função (Ponteiro para função)
typedef void (*pFuncao)(void *);

typedef struct{
    pFuncao ptr; // Ponteiro para a função do estado atual
    unsigned char firstTime; // Indica se é a primeira vez que o estado está sendo executado
}StateMachine;

//Definiçoes
#define STATE(name)         void name(StateMachine *_sm_) // Define um estado da máquina de estados
#define NEXT_STATE(name)    _sm_->ptr = (pFuncao)name // Define o próximo estado da máquina de estados
#define INIT(sm,name)       {smBlink.ptr = (pFuncao)name;smBlink.firstTime=1;} // Inicializa a máquina de estados com o estado inicial
#define EXEC(sm)			{pFuncao temp=smBlink.ptr;smBlink.ptr(&smBlink);smBlink.firstTime=(temp != smBlink.ptr);} // Executa o estado atual da máquina de estados
#define FIRST               (_sm_->firstTime) // Retorna TRUE se for a primeira vez que o estado está sendo executado
#define COMPARE(sm,name)    (smBlink.ptr == (pFuncao)name) // Verifica se a máquina de estados estado em um estado desejado

#endif // SM_H
