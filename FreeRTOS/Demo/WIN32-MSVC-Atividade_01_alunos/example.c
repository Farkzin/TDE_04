#include "FreeRTOS.h"
#include "task.h"
#include "basic_io.h"
#include "hal.h"
#include "sm.h"

#define TEMPO_INVERTER_MS	333 // Tempo em milissegundos para inverter o estado do pisca-alerta (1.5 Hz)

StateMachine smBlink; // Variável do tipo struct que possui um ponteiro para a função do estado atual e um indicador de primeira execução

// Declaração dos estados da máquina de estados
STATE(state_BLINK_NONE);
STATE(state_BLINK_LEFT);
STATE(state_BLINK_RIGHT);
STATE(state_BLINK_ALERT);

// Estado em que nenhum sinalizador está ativo
STATE(state_BLINK_NONE) {
	tuCommand cmd = getTurnCommand();

	if (cmd.Alert)                                  NEXT_STATE(state_BLINK_ALERT);
	else if (cmd.TurnCommands == command_Left)      NEXT_STATE(state_BLINK_LEFT);
	else if (cmd.TurnCommands == command_Right)     NEXT_STATE(state_BLINK_RIGHT);
}

// Estado em que o sinalizador esquerdo está ativo
STATE(state_BLINK_LEFT) {
	tuCommand cmd = getTurnCommand();

	if (cmd.Alert)                                  NEXT_STATE(state_BLINK_ALERT);
	else if (cmd.TurnCommands == command_Right)     NEXT_STATE(state_BLINK_RIGHT);
	else if (cmd.TurnCommands == command_None)      NEXT_STATE(state_BLINK_NONE);
}

// Estado em que o sinalizador direito está ativo
STATE(state_BLINK_RIGHT) {
	tuCommand cmd = getTurnCommand();

	if (cmd.Alert)                                  NEXT_STATE(state_BLINK_ALERT);
	else if (cmd.TurnCommands == command_Left)      NEXT_STATE(state_BLINK_LEFT);
	else if (cmd.TurnCommands == command_None)      NEXT_STATE(state_BLINK_NONE);
}

// Estado em que o sinalizador de alerta está ativo
STATE(state_BLINK_ALERT) {
	tuCommand cmd = getTurnCommand();

	if (!cmd.Alert) {
		if (cmd.TurnCommands == command_Left)       NEXT_STATE(state_BLINK_LEFT);
		else if (cmd.TurnCommands == command_Right) NEXT_STATE(state_BLINK_RIGHT);
		else                                        NEXT_STATE(state_BLINK_NONE);
	}
}

// Função que retorna TRUE se a fase do pisca-alerta estiver acesa
static boolean faseAcesa(void) {
	// Cálculo: divide o tempo atual em ticks pelo tempo de inversão em ticks e pega o resto da divisão por 2 para alternar entre TRUE e FALSE
	return (boolean)((xTaskGetTickCount() / (TEMPO_INVERTER_MS / portTICK_PERIOD_MS)) % 2);
}

// Task que controla o pisca-alerta esquerdo
void task_BlinkLeft(void *pParam) {
	for (;;) {
		if (COMPARE(smBlink, state_BLINK_LEFT) || COMPARE(smBlink, state_BLINK_ALERT)) {
			TurnSignalLeft(faseAcesa());
		}
		else {
			TurnSignalLeft(FALSE);
		}
		vTaskDelay(10 / portTICK_PERIOD_MS); // Aguarda 10 ms antes de verificar novamente o estado do pisca-alerta esquerdo
	}
}

// Task que controla o pisca-alerta direito
void task_BlinkRight(void *pParam) {
	for (;;) {
		if (COMPARE(smBlink, state_BLINK_RIGHT) || COMPARE(smBlink, state_BLINK_ALERT)) {
			TurnSignalRight(faseAcesa());
		}
		else {
			TurnSignalRight(FALSE);
		}
		vTaskDelay(10 / portTICK_PERIOD_MS); // Aguarda 10 ms antes de verificar novamente o estado do pisca-alerta direito
	}
}

// Task que executa a máquina de estados do pisca-alerta
void task_StateMachine(void *pParam) {
	for (;;) {
		EXEC(smBlink);
		vTaskDelay(10 / portTICK_PERIOD_MS); // Aguarda 10 ms antes de executar novamente a máquina de estados
	}
}

int main_(void)
{
	InitHAL(); 
	INIT(smBlink, state_BLINK_NONE); // Inicializa a máquina de estados do pisca-alerta com o estado NONE

	// Cria as tasks responsáveis por controlar a máquina de estados e os sinais de pisca-alerta esquerdo e direito
	// Prioridades: teclado (3) > máquina de estados (2) > sinalizadores (1), para que no mesmo tick a entrada seja lida, depois o estado atualizado e por último as lâmpadas
	xTaskCreate(task_StateMachine, "StateMachine", configMINIMAL_STACK_SIZE, NULL, 2, NULL);
	xTaskCreate(task_BlinkLeft,    "BlinkLeft",    configMINIMAL_STACK_SIZE, NULL, 1, NULL);
	xTaskCreate(task_BlinkRight,   "BlinkRight",   configMINIMAL_STACK_SIZE, NULL, 1, NULL);

	vTaskStartScheduler(); // Inicia o escalonador do FreeRTOS, que passa a executar as tasks criadas
	return 0;
}
