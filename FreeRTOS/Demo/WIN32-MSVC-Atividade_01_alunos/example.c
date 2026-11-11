
/* FreeRTOS.org includes. */
#include "FreeRTOS.h"
#include "task.h"

// Demais includes
#include "basic_io.h"
#include "hal.h"
#include "sm.h"

// Frequencia de 1,5 Hz = 1,5 piscadas por segundo.
// Uma piscada completa (acende + apaga) dura 1000/1,5 = 666 ms,
// entao o pino muda de valor a cada 333 ms.
#define TEMPO_INVERTER_MS	333

// Esta sera a sua maquina de estados
StateMachine smBlink;

// Assinaturas dos 4 estados da maquina de estados
STATE(state_BLINK_NONE);
STATE(state_BLINK_LEFT);
STATE(state_BLINK_RIGHT);
STATE(state_BLINK_ALERT);

// Codigo dos estados.
// Em todos: le a alavanca/botao e decide para qual estado ir.

// Nenhum sinalizador piscando
STATE(state_BLINK_NONE) {
	tuCommand cmd = getTurnCommand();

	if (cmd.Alert)                                  NEXT_STATE(state_BLINK_ALERT);	// pisca-alerta tem prioridade
	else if (cmd.TurnCommands == command_Left)      NEXT_STATE(state_BLINK_LEFT);
	else if (cmd.TurnCommands == command_Right)     NEXT_STATE(state_BLINK_RIGHT);
}

// Sinalizador esquerdo piscando
STATE(state_BLINK_LEFT) {
	tuCommand cmd = getTurnCommand();

	if (cmd.Alert)                                  NEXT_STATE(state_BLINK_ALERT);
	else if (cmd.TurnCommands == command_Right)     NEXT_STATE(state_BLINK_RIGHT);
	else if (cmd.TurnCommands == command_None)      NEXT_STATE(state_BLINK_NONE);
}

// Sinalizador direito piscando
STATE(state_BLINK_RIGHT) {
	tuCommand cmd = getTurnCommand();

	if (cmd.Alert)                                  NEXT_STATE(state_BLINK_ALERT);
	else if (cmd.TurnCommands == command_Left)      NEXT_STATE(state_BLINK_LEFT);
	else if (cmd.TurnCommands == command_None)      NEXT_STATE(state_BLINK_NONE);
}

// Pisca-alerta: os dois piscando
STATE(state_BLINK_ALERT) {
	tuCommand cmd = getTurnCommand();

	// Ao sair do alerta, respeita a posicao atual da alavanca
	if (!cmd.Alert) {
		if (cmd.TurnCommands == command_Left)       NEXT_STATE(state_BLINK_LEFT);
		else if (cmd.TurnCommands == command_Right) NEXT_STATE(state_BLINK_RIGHT);
		else                                        NEXT_STATE(state_BLINK_NONE);
	}
}

// Codigos das Tasks

// Diz se o sinalizador deve estar ACESO neste instante.
// Usa o relogio do sistema (ticks): a cada 333 ms o valor alterna entre 0 e 1.
// Como as duas tasks usam o MESMO relogio, esquerdo e direito ficam sempre sincronizados.
static boolean faseAcesa(void) {
	return (boolean)((xTaskGetTickCount() / (TEMPO_INVERTER_MS / portTICK_PERIOD_MS)) % 2);
}

// Pisca o sinalizador esquerdo (so nos estados LEFT e ALERT)
void task_BlinkLeft(void *pParam) {
	for (;;) {
		if (COMPARE(smBlink, state_BLINK_LEFT) || COMPARE(smBlink, state_BLINK_ALERT)) {
			TurnSignalLeft(faseAcesa());	// acende/apaga conforme o relogio
		}
		else {
			TurnSignalLeft(FALSE);			// outros estados: garante apagado
		}
		vTaskDelay(10 / portTICK_PERIOD_MS);
	}
}

// Pisca o sinalizador direito (so nos estados RIGHT e ALERT)
void task_BlinkRight(void *pParam) {
	for (;;) {
		if (COMPARE(smBlink, state_BLINK_RIGHT) || COMPARE(smBlink, state_BLINK_ALERT)) {
			TurnSignalRight(faseAcesa());
		}
		else {
			TurnSignalRight(FALSE);
		}
		vTaskDelay(10 / portTICK_PERIOD_MS);
	}
}

// Executa a maquina de estados continuamente
void task_StateMachine(void *pParam) {
	for (;;) {
		EXEC(smBlink);
		vTaskDelay(10 / portTICK_PERIOD_MS);
	}
}

int main_(void)
{
	InitHAL();							// liga o HAL (cria a task do teclado)
	INIT(smBlink, state_BLINK_NONE);	// estado inicial: nada piscando

	xTaskCreate(task_StateMachine, "StateMachine", configMINIMAL_STACK_SIZE, NULL, 1, NULL);
	xTaskCreate(task_BlinkLeft,    "BlinkLeft",    configMINIMAL_STACK_SIZE, NULL, 1, NULL);
	xTaskCreate(task_BlinkRight,   "BlinkRight",   configMINIMAL_STACK_SIZE, NULL, 1, NULL);

	vTaskStartScheduler();				// entrega o controle ao FreeRTOS
	return 0;
}
