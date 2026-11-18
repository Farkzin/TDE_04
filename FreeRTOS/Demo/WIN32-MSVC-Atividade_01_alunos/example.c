#include "FreeRTOS.h"
#include "task.h"
#include "basic_io.h"
#include "hal.h"
#include "sm.h"

#define TEMPO_INVERTER_MS	333 // Tempo em milissegundos para inverter o estado do pisca-alerta (1.5 Hz)

StateMachine smBlink; // Variável do tipo struct que possui um ponteiro para a função do estado atual e um indicador de primeira execução

TaskHandle_t xHandleBlinkLeft  = NULL; // Handle (manuseador) da task do pisca esquerdo. NULL significa que a task não existe
TaskHandle_t xHandleBlinkRight = NULL; // Handle (manuseador) da task do pisca direito. NULL significa que a task não existe

// Declaração dos estados da máquina de estados
STATE(state_BLINK_NONE);
STATE(state_BLINK_LEFT);
STATE(state_BLINK_RIGHT);
STATE(state_BLINK_ALERT);

// Função que inverte a lampada a cada 333 ms (1.5 Hz)
static boolean faseAcesa(void) {
	return (xTaskGetTickCount() / TEMPO_INVERTER_MS) % 2; // Pega o resto da divisão inteira do tempo atual pelo tempo de inversão
}

// Task que controla o pisca-alerta esquerdo. Ela só existe enquanto o pisca esquerdo precisa estar ativo, por isso não precisa consultar a máquina de estados
void task_BlinkLeft(void *pParam) {
	for (;;) {
		TurnSignalLeft(faseAcesa());
		vTaskDelay(10); // Espera 10 ms para as outras tasks do FreeRTOS serem executadas
	}
}

// Task que controla o pisca-alerta direito. Ela só existe enquanto o pisca direito precisa estar ativo, por isso não precisa consultar a máquina de estados
void task_BlinkRight(void *pParam) {
	for (;;) {
		TurnSignalRight(faseAcesa());
		vTaskDelay(10); // Espera 10 ms para as outras tasks do FreeRTOS serem executadas
	}
}

// Cria dinamicamente a task do pisca esquerdo (se ela ainda não existir)
static void startBlinkLeft(void) {
	if (xHandleBlinkLeft == NULL) {
		xTaskCreate(task_BlinkLeft, "BlinkLeft", configMINIMAL_STACK_SIZE, NULL, 1, &xHandleBlinkLeft); // Guarda o handle para poder deletar a task depois
	}
}

// Cria dinamicamente a task do pisca direito (se ela ainda não existir)
static void startBlinkRight(void) {
	if (xHandleBlinkRight == NULL) {
		xTaskCreate(task_BlinkRight, "BlinkRight", configMINIMAL_STACK_SIZE, NULL, 1, &xHandleBlinkRight); // Guarda o handle para poder deletar a task depois
	}
}

// Deleta a task do pisca esquerdo (se ela existir) e apaga a lampada, pois a task não faz mais isso
static void stopBlinkLeft(void) {
	if (xHandleBlinkLeft != NULL) {
		vTaskDelete(xHandleBlinkLeft); // Deleta a task usando o handle guardado na criação
		xHandleBlinkLeft = NULL;       // Marca que a task não existe mais
	}
	TurnSignalLeft(FALSE);             // A lampada pode ter ficado acesa quando a task foi deletada
}

// Deleta a task do pisca direito (se ela existir) e apaga a lampada, pois a task não faz mais isso
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

// Executa a máquina de estados do pisca-alerta. É chamada pela Idle Hook (vApplicationIdleHook em main.c), ou seja, só roda quando nenhuma outra task precisa do processador
// Não pode bloquear (sem vTaskDelay) e precisa sempre retornar, para a Idle Task continuar fazendo a limpeza das tasks deletadas
void idle_StateMachine(void) {
	EXEC(smBlink);
}

int main_(void)
{
	InitHAL(); // Cria a task do teclado (prioridade 3)
	INIT(smBlink, state_BLINK_NONE); // Inicializa a máquina de estados do pisca-alerta com o estado NONE

	// Nenhuma task do pisca é criada aqui: a máquina de estados cria e deleta task_BlinkLeft e task_BlinkRight dinamicamente (prioridade 1), conforme os comandos recebidos
	// Prioridades: teclado (3) > sinalizadores (1) > máquina de estados (Idle Task, 0), que só executa quando todas as outras tasks estão bloqueadas

	vTaskStartScheduler(); // Inicia o escalonador do FreeRTOS, que passa a executar as tasks criadas
	return 0;
}
