#include "FreeRTOS.h"
#include "task.h"
#include "basic_io.h"
#include "hal.h"
#include "sm.h"

#define TEMPO_INVERTER_MS	333 // Tempo em milissegundos para inverter o estado do pisca-alerta (1.5 Hz)

StateMachine smBlink; // Variável do tipo struct que possui um ponteiro para a função do estado atual e um indicador de primeira execução

// Handle's para saber se as tasks existem ou não
TaskHandle_t xHandleBlinkLeft  = NULL;
TaskHandle_t xHandleBlinkRight = NULL; 

// Declaração dos estados da máquina de estados
STATE(state_BLINK_NONE);
STATE(state_BLINK_LEFT);
STATE(state_BLINK_RIGHT);
STATE(state_BLINK_ALERT);

// Função que inverte a lampada a cada 333 ms (1.5 Hz)
static boolean faseAcesa(void) {
	return (xTaskGetTickCount() / TEMPO_INVERTER_MS) % 2; // Pega o resto da divisão inteira do tempo atual pelo tempo de inversão
}

// Task que controla o pisca-alerta esquerdo. Apenas acende a lampada enquanto a task existir
void task_BlinkLeft(void *pParam) {
	for (;;) {
		TurnSignalLeft(faseAcesa());
		vTaskDelay(10); // Espera 10 ms para as outras tasks do FreeRTOS serem executadas
	}
}

// Task que controla o pisca-alerta direito. Apenas acende a lampada enquanto a task existir
void task_BlinkRight(void *pParam) {
	for (;;) {
		TurnSignalRight(faseAcesa());
		vTaskDelay(10); // Espera 10 ms para as outras tasks do FreeRTOS serem executadas
	}
}

// Se a task do pisca esquerdo não existir, cria dinamicamente a task do pisca esquerdo
static void startBlinkLeft(void) {
	if (xHandleBlinkLeft == NULL) {
		xTaskCreate(task_BlinkLeft, "BlinkLeft", configMINIMAL_STACK_SIZE, NULL, 1, &xHandleBlinkLeft); // Guarda o handle para poder deletar a task depois
	}
}

// Se a task do pisca direito não existir, cria dinamicamente a task do pisca direito
static void startBlinkRight(void) {
	if (xHandleBlinkRight == NULL) {
		xTaskCreate(task_BlinkRight, "BlinkRight", configMINIMAL_STACK_SIZE, NULL, 1, &xHandleBlinkRight); // Guarda o handle para poder deletar a task depois
	}
}

// Se a task do pisca esquerdo existir, deleta a task do pisca esquerdo e apaga a lampada
static void stopBlinkLeft(void) {
	if (xHandleBlinkLeft != NULL) {
		vTaskDelete(xHandleBlinkLeft); // Deleta a task usando o handle guardado na criação
		xHandleBlinkLeft = NULL;       // Marca que a task não existe mais
	}
	TurnSignalLeft(FALSE);             // A lampada pode ter ficado acesa quando a task foi deletada
}

// Se a task do pisca direito existir, deleta a task do pisca direito e apaga a lampada
static void stopBlinkRight(void) {
	if (xHandleBlinkRight != NULL) {
		vTaskDelete(xHandleBlinkRight); // Deleta a task usando o handle guardado na criação
		xHandleBlinkRight = NULL;       // Marca que a task não existe mais
	}
	TurnSignalRight(FALSE);             // A lampada pode ter ficado acesa quando a task foi deletada
}

// Estado em que nenhum sinalizador está ativo
STATE(state_BLINK_NONE) {
	tuCommand cmd;

	if (FIRST) {                // Só na primeira execução do estado, para não criar/deletar tasks a cada chamada
		stopBlinkLeft();
		stopBlinkRight();
	}

	cmd = getTurnCommand();

	if (cmd.Alert)                                  NEXT_STATE(state_BLINK_ALERT);
	else if (cmd.TurnCommands == command_Left)      NEXT_STATE(state_BLINK_LEFT);
	else if (cmd.TurnCommands == command_Right)     NEXT_STATE(state_BLINK_RIGHT);
}

// Estado em que o sinalizador esquerdo está ativo
STATE(state_BLINK_LEFT) {
	tuCommand cmd;

	if (FIRST) {                // Só na primeira execução do estado, para não criar/deletar tasks a cada chamada
		startBlinkLeft();
		stopBlinkRight();
	}

	cmd = getTurnCommand();

	if (cmd.Alert)                                  NEXT_STATE(state_BLINK_ALERT);
	else if (cmd.TurnCommands == command_Right)     NEXT_STATE(state_BLINK_RIGHT);
	else if (cmd.TurnCommands == command_None)      NEXT_STATE(state_BLINK_NONE);
}

// Estado em que o sinalizador direito está ativo
STATE(state_BLINK_RIGHT) {
	tuCommand cmd;

	if (FIRST) {                // Só na primeira execução do estado, para não criar/deletar tasks a cada chamada
		startBlinkRight();
		stopBlinkLeft();
	}

	cmd = getTurnCommand();

	if (cmd.Alert)                                  NEXT_STATE(state_BLINK_ALERT);
	else if (cmd.TurnCommands == command_Left)      NEXT_STATE(state_BLINK_LEFT);
	else if (cmd.TurnCommands == command_None)      NEXT_STATE(state_BLINK_NONE);
}

// Estado em que o sinalizador de alerta está ativo
STATE(state_BLINK_ALERT) {
	tuCommand cmd;

	if (FIRST) {                // Só na primeira execução do estado, para não criar/deletar tasks a cada chamada
		startBlinkLeft();       // No alerta as duas tasks existem e piscam juntas (mesma fase em faseAcesa)
		startBlinkRight();
	}

	cmd = getTurnCommand();

	if (!cmd.Alert) {
		if (cmd.TurnCommands == command_Left)       NEXT_STATE(state_BLINK_LEFT);
		else if (cmd.TurnCommands == command_Right) NEXT_STATE(state_BLINK_RIGHT);
		else                                        NEXT_STATE(state_BLINK_NONE);
	}
}

// Executa a máquina de estados do pisca-alerta no Idle Hook
void idle_StateMachine(void) {
	EXEC(smBlink);
}

int main_(void)
{
	InitHAL(); 
	INIT(smBlink, state_BLINK_NONE); // Inicializa a máquina de estados do pisca-alerta no estado NONE
	vTaskStartScheduler(); // Inicia o escalonador do FreeRTOS, que passa a executar as tasks criadas
	return 0;
}
