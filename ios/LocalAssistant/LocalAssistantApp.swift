import AppIntents
import SwiftUI

@main
struct LocalAssistantApp: App {
    init() {
        LocalAssistantShortcuts.updateAppShortcutParameters()
    }

    var body: some Scene {
        WindowGroup { ContentView() }
    }
}

struct LocalAssistantShortcuts: AppShortcutsProvider {
    static var appShortcuts: [AppShortcut] {
        AppShortcut(
            intent: AskLocalAssistantIntent(),
            phrases: ["问 \(.applicationName)", "用 \(.applicationName)"],
            shortTitle: "问本地助手",
            systemImageName: "location.magnifyingglass"
        )
    }
}

struct AskLocalAssistantIntent: AppIntent {
    static var title: LocalizedStringResource = "问本地助手"
    static var description = IntentDescription("查询附近地点、路线和高德导航")

    @Parameter(title: "你想做什么", requestValueDialog: "请说出要查找的地点或路线。")
    var request: String

    static var parameterSummary: some ParameterSummary {
        Summary("用本地助手处理 \(\.$request)")
    }

    func perform() async throws -> some IntentResult & ProvidesDialog & ShowsSnippetView {
        let location = await LocationService().current()
        let response: TurnResponse
        do {
            response = try await Gateway().send(text: request, location: location)
        } catch {
            return .result(dialog: IntentDialog(LocalizedStringResource(stringLiteral: error.localizedDescription)),
                           view: TurnSnippet(response: nil, message: error.localizedDescription))
        }
        return .result(dialog: IntentDialog(LocalizedStringResource(stringLiteral: response.spoken)),
                       view: TurnSnippet(response: response, message: nil))
    }
}

struct TurnSnippet: View {
    let response: TurnResponse?
    let message: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(message ?? response?.spoken ?? "").font(.headline)
            ForEach(Array(response?.places.prefix(3) ?? [])) { place in
                Text("\(place.name) · \(place.distance_m) 米")
            }
            if let action = response?.action,
               action.requires_confirmation,
               let url = URL(string: action.url), url.scheme == "iosamap" {
                Link("确认并打开高德", destination: url)
            }
        }
        .padding()
    }
}
