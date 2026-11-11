#ifndef SM_H
#define SM_H

//Criando a variavel prt apontando para função (Ponteiro para função)
typedef void (*pFuncao)(void *);

typedef struct{
    pFuncao ptr;
    unsigned char firstTime;
}StateMachine;

//Definiçoes
#define STATE(name)         void name(StateMachine *_sm_)
#define NEXT_STATE(name)    _sm_->ptr = (pFuncao)name
#define INIT(sm,name)       {smBlink.ptr = (pFuncao)name;smBlink.firstTime=1;}
#define EXEC(sm)			{pFuncao temp=smBlink.ptr;smBlink.ptr(&smBlink);smBlink.firstTime=(temp != smBlink.ptr);}
#define FIRST               (_sm_->firstTime)
#define COMPARE(sm,name)    (smBlink.ptr == (pFuncao)name)

#endif // SM_H
