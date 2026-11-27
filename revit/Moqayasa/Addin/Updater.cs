using Autodesk.Revit.UI;
using Autodesk.Revit.UI.Events;
using Moqayasa.Core;

namespace Moqayasa;

/// <summary>
/// Checks version.json once at startup in the background (silent when offline), then shows one TaskDialog on Revit's own thread.
/// Nothing is downloaded or installed automatically: the button opens the download page.
/// </summary>
static class Updater
{
    static UpdateInfo? _found;
    static string SkipFile => Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "Moqayasa", "update_skip.txt");

    public static void Start(UIControlledApplication app)
    {
        try
        {
            System.Threading.Tasks.Task.Run(() =>
            {
                try
                {
                    var info = Update.Parse(Fetcher.Get(Update.VersionUrl));
                    string? skipped = File.Exists(SkipFile) ? File.ReadAllText(SkipFile).Trim() : null;
                    if (Update.ShouldOffer(info, Update.Current, skipped)) _found = info;
                }
                catch { /* offline or blocked: say nothing */ }
            });
            app.Idling += OnIdling;
        }
        catch { }
    }

    static int _ticks;
    static void OnIdling(object? sender, IdlingEventArgs e)
    {
        // wait for the network check, but give up after a while so Idling is not hooked forever
        if (_found is null) { if (++_ticks > 600 && sender is UIApplication) Detach(sender); return; }
        var info = _found; _found = null; Detach(sender);
        try
        {
            var td = new TaskDialog("مقايسة: تحديث جديد")
            {
                MainInstruction = $"فيه نسخة أحدث من مقايسة: {info!.Version} (عندك {Update.Current})",
                MainContent = (string.IsNullOrWhiteSpace(info.ChangelogAr) ? info.ChangelogEn : info.ChangelogAr) + "\n\nمش بيتسطب لوحده: الزرار بيفتح صفحة التحميل وانت اللي بتشغّل install.ps1.",
                CommonButtons = TaskDialogCommonButtons.Close,
            };
            td.AddCommandLink(TaskDialogCommandLinkId.CommandLink1, "تحميل النسخة الجديدة");
            td.AddCommandLink(TaskDialogCommandLinkId.CommandLink2, "تخطي هذه النسخة");
            var r = td.Show();
            if (r == TaskDialogResult.CommandLink1) System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo(info.Download) { UseShellExecute = true });
            if (r == TaskDialogResult.CommandLink2) { Directory.CreateDirectory(Path.GetDirectoryName(SkipFile)!); File.WriteAllText(SkipFile, info.Version); }
        }
        catch { }
    }

    static void Detach(object? sender)
    {
        try { if (sender is UIApplication ua) ua.Idling -= OnIdling; } catch { }
    }
}
