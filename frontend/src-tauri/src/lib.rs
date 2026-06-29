// Integração do backend (FastAPI) como "sidecar": um executável separado
// (gerado do Python com PyInstaller) que o app inicia junto com a janela e
// encerra quando a janela fecha. O frontend fala com ele em 127.0.0.1:8000.

use std::sync::Mutex;
use tauri::Manager;
use tauri_plugin_shell::process::CommandChild;
use tauri_plugin_shell::ShellExt;

// Guarda o processo do backend para podermos encerrá-lo ao fechar o app.
struct Backend(Mutex<Option<CommandChild>>);

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(Backend(Mutex::new(None)))
        .setup(|app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }

            // Inicia o backend empacotado (sidecar "analise-backend").
            let sidecar = app
                .shell()
                .sidecar("analise-backend")
                .expect("sidecar analise-backend não encontrado")
                // Sinaliza ao backend que ele é um sidecar: assim ele vigia o
                // stdin e se encerra sozinho se este app morrer (inclusive em
                // crash/force-kill, quando o evento de fechar janela não roda).
                .env("ANALISE_SIDECAR", "1");
            let (_rx, child) = sidecar.spawn().expect("falha ao iniciar o backend");
            app.state::<Backend>().0.lock().unwrap().replace(child);

            Ok(())
        })
        .on_window_event(|window, event| {
            // Ao fechar a janela, encerra o backend para não deixar processo órfão.
            if let tauri::WindowEvent::Destroyed = event {
                if let Some(child) = window
                    .app_handle()
                    .state::<Backend>()
                    .0
                    .lock()
                    .unwrap()
                    .take()
                {
                    let _ = child.kill();
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
