#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"
#include "basic_io.h"
#include "hal.h"
#include "sm.h"

#define TEMPO_INVERTER_MS	333 // Tempo em milissegundos para inverter o estado do pisca-alerta (1.5 Hz)

StateMachine smBlink; // Variável do tipo struct que possui um ponteiro para a função do estado atual e um indicador de primeira execução

// Parâmetro da task_Blink: o callback (ponteiro de função) do lado que ela deve piscar e o handle da task criada
typedef struct {
	void (*TurnSignal)(boolean s); // Callback: TurnSignalLeft ou TurnSignalRight
	TaskHandle_t handle;           // NULL = task não existe
} tBlink;

static tBlink blinkLeft  = { TurnSignalLeft,  NULL };
static tBlink blinkRight = { TurnSignalRight, NULL };

// Declaração dos estados da máquina de estados
STATE(state_BLINK_NONE);
STATE(state_BLINK_LEFT);
STATE(state_BLINK_RIGHT);
STATE(state_BLINK_ALERT);

// Função que inverte a lampada a cada 333 ms (1.5 Hz)
static boolean faseAcesa(void) {
	return (xTaskGetTickCount() / TEMPO_INVERTER_MS) % 2; // Pega o resto da divisão inteira do tempo atual pelo tempo de inversão
}

// Uma única task para os dois lados: pisca a lâmpada chamando o callback recebido como parâmetro
void task_Blink(void *pParam) {
	tBlink *blink = (tBlink *)pParam;

	for (;;) {
		blink->TurnSignal(faseAcesa()); // Chama TurnSignalLeft ou TurnSignalRight, conforme a instância
		vTaskDelay(10); // Espera 10 ms para as outras tasks do FreeRTOS serem executadas
	}
}

// Se a task do lado pedido não existir, cria uma instância da task_Blink passando o lado como parâmetro
static void startBlink(tBlink *blink) {
	if (blink->handle == NULL) {
		xTaskCreate(task_Blink, "Blink", configMINIMAL_STACK_SIZE, blink, 1, &blink->handle); // Guarda o handle para poder deletar a task depois
	}
}

// Se a task do lado pedido existir, deleta a task e apaga a lâmpada
static void stopBlink(tBlink *blink) {
	if (blink->handle != NULL) {
		vTaskDelete(blink->handle); // Deleta a task usando o handle guardado na criação
		blink->handle = NULL;       // Marca que a task não existe mais
	}
	blink->TurnSignal(FALSE);       // A lâmpada pode ter ficado acesa quando a task foi deletada
}

// Espera (em estado blocked) até a task_Key mandar um comando pela fila
static tuCommand waitCommand(void) {
	tuCommand cmd;

	xQueueReceive(xQueueCommand, &cmd, portMAX_DELAY);
	BrakeLight(cmd.Brake); // O freio não depende do pisca, então é atualizado a cada comando recebido
	return cmd;
}

// Estado em que nenhum sinalizador está ativo
STATE(state_BLINK_NONE) {
	tuCommand cmd;

	if (FIRST) {                // Só na primeira execução do estado, para não criar/deletar tasks a cada chamada
		stopBlink(&blinkLeft);
		stopBlink(&blinkRight);
	}

	cmd = waitCommand();

	if (cmd.Alert)                                                  NEXT_STATE(state_BLINK_ALERT);
	else if (cmd.Ignition && cmd.TurnCommands == command_Left)      NEXT_STATE(state_BLINK_LEFT);
	else if (cmd.Ignition && cmd.TurnCommands == command_Right)     NEXT_STATE(state_BLINK_RIGHT);
}

// Estado em que o sinalizador esquerdo está ativo
STATE(state_BLINK_LEFT) {
	tuCommand cmd;

	if (FIRST) {                // Só na primeira execução do estado, para não criar/deletar tasks a cada chamada
		startBlink(&blinkLeft);
		stopBlink(&blinkRight);
	}

	cmd = waitCommand();

	if (cmd.Alert)                                                  NEXT_STATE(state_BLINK_ALERT);
	else if (!cmd.Ignition || cmd.TurnCommands == command_None)     NEXT_STATE(state_BLINK_NONE);
	else if (cmd.TurnCommands == command_Right)                     NEXT_STATE(state_BLINK_RIGHT);
}

// Estado em que o sinalizador direito está ativo
STATE(state_BLINK_RIGHT) {
	tuCommand cmd;

	if (FIRST) {                // Só na primeira execução do estado, para não criar/deletar tasks a cada chamada
		startBlink(&blinkRight);
		stopBlink(&blinkLeft);
	}

	cmd = waitCommand();

	if (cmd.Alert)                                                  NEXT_STATE(state_BLINK_ALERT);
	else if (!cmd.Ignition || cmd.TurnCommands == command_None)     NEXT_STATE(state_BLINK_NONE);
	else if (cmd.TurnCommands == command_Left)                      NEXT_STATE(state_BLINK_LEFT);
}

// Estado em que o sinalizador de alerta está ativo (funciona com a ignição ligada ou desligada)
STATE(state_BLINK_ALERT) {
	tuCommand cmd;

	if (FIRST) {                // Só na primeira execução do estado, para não criar/deletar tasks a cada chamada
		startBlink(&blinkLeft);  // No alerta as duas tasks existem e piscam juntas (mesma fase em faseAcesa)
		startBlink(&blinkRight);
	}

	cmd = waitCommand();

	if (!cmd.Alert) {
		if (cmd.Ignition && cmd.TurnCommands == command_Left)       NEXT_STATE(state_BLINK_LEFT);
		else if (cmd.Ignition && cmd.TurnCommands == command_Right) NEXT_STATE(state_BLINK_RIGHT);
		else                                                        NEXT_STATE(state_BLINK_NONE);
	}
}

// Task da máquina de estados: fica em blocked dentro de waitCommand() enquanto a fila estiver vazia
void task_StateMachine(void *pParam) {
	for (;;) {
		EXEC(smBlink);
	}
}

int main_(void)
{
	InitHAL(); 
	INIT(smBlink, state_BLINK_NONE); // Inicializa a máquina de estados do pisca-alerta no estado NONE
	xTaskCreate(task_StateMachine, "StateMachine", configMINIMAL_STACK_SIZE, NULL, 2, NULL);
	vTaskStartScheduler(); // Inicia o escalonador do FreeRTOS, que passa a executar as tasks criadas
	return 0;
}
