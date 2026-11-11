#ifndef __HAL__
#define __HAL__

#include "datatypes.h"

/*	tdTurningCommands é um tipo de dado que enumera quais os possíveis valores enviados pela Camada de Abstracao de Hardware como
	resposta aos comandos da alavanca de comando dos sinalizadores ("alavanda das setas junto ao volante")
*/
typedef enum {
	command_None,	// A alavanca está na posicao central
	command_Left,	// A alavanca está na posicao de "seta para a esquerda"
	command_Right	// A alavanca está na posicao de "seta para a direita"
} tdTurningCommands;

/*	tuCommand é um tipo de dado que possui uma estrutura com as informacoes sobre os sinalizadores.
	- TurnCommands: o comando da alavanca de comando dos sinalizadores ("alavanda das setas junto ao volante"). Ver também tdTurningCommands
	- Alert: indica se o Pisca-Alerta esta ou nao ligado
*/
typedef struct {
		tdTurningCommands TurnCommands : 3;
		uint8 Alert : 1;
} tuCommand;

// Inicializa a Camada de Abstracao de Hardware.
void InitHAL();

// Metodo que retorna o estado da  alavanca de comando dos sinalizadores ("alavanda das setas junto ao volante"). Ver também tuCommand
tuCommand getTurnCommand();

/* Liga ou desliga o sinalizador direito.
	- s: estado do sinalizador (TRUE = acende / FALSE = apaga)
*/
void TurnSignalRight(boolean s);

/* Liga ou desliga o sinalizador esquerdo.
- s: estado do sinalizador (TRUE = acende / FALSE = apaga)
*/
void TurnSignalLeft(boolean s);

// Inverte o estado do sinalizador direito. Se estava apagado, acende. Se estava aceso, apaga.
void ToggleTurnSignalRight();

// Inverte o estado do sinalizador esquerdo. Se estava apagado, acende. Se estava aceso, apaga.
void ToggleTurnSignalLeft();

#endif
