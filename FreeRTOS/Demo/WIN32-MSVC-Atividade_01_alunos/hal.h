#ifndef __HAL__
#define __HAL__

#include "datatypes.h"
#include "FreeRTOS.h"
#include "queue.h"

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
	- Ignition: indica se a ignicao esta ou nao ligada
	- Brake: indica se o freio esta ou nao acionado
*/
typedef struct {
		tdTurningCommands TurnCommands : 3;
		uint8 Alert : 1;
		uint8 Ignition : 1;
		uint8 Brake : 1;
} tuCommand;

// Fila por onde a task_Key envia um tuCommand para a task_StateMachine a cada tecla apertada
extern QueueHandle_t xQueueCommand;

// Inicializa a Camada de Abstracao de Hardware.
void InitHAL();

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

/* Liga ou desliga a luz de freio (comanda os dois lados).
- s: estado da luz de freio (TRUE = acende / FALSE = apaga)
*/
void BrakeLight(boolean s);

#endif
