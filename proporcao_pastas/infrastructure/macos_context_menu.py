"""Integracao opcional com as Acoes Rapidas (Servicos) do Finder no macOS."""
import os
import plistlib
import shutil
import subprocess
import sys
import uuid


def configure_macos_context_menu(script_path: str, remove: bool = False) -> None:
    services_dir = os.path.expanduser("~/Library/Services")
    workflow_dir = os.path.join(services_dir, "Ver proporcao de pastas.workflow")

    if remove:
        if os.path.exists(workflow_dir):
            shutil.rmtree(workflow_dir, ignore_errors=True)
        print("Ação Rápida removida do Finder.")
        return

    contents_dir = os.path.join(workflow_dir, "Contents")
    os.makedirs(contents_dir, exist_ok=True)

    info_plist = {
        "NSServices": [
            {
                "NSMenuItem": {"default": "Ver proporção de pastas"},
                "NSMessage": "runWorkflowAsService",
                "NSRequiredContext": {"NSApplicationIdentifier": "com.apple.finder"},
                "NSSendFileTypes": ["public.folder"],
            }
        ]
    }
    with open(os.path.join(contents_dir, "Info.plist"), "wb") as f:
        plistlib.dump(info_plist, f)

    action_uuid = str(uuid.uuid4()).upper()
    input_uuid = str(uuid.uuid4()).upper()
    output_uuid = str(uuid.uuid4()).upper()
    command_str = f'"{sys.executable}" "{script_path}" "$1" >/dev/null 2>&1 &'

    document_wflow = {
        "AMApplicationBuild": "523",
        "AMApplicationVersion": "2.10",
        "AMDocumentVersion": "2",
        "actions": [
            {
                "action": {
                    "AMAccepts": {
                        "Container": "List",
                        "Optional": True,
                        "Types": ["com.apple.cocoa.string"],
                    },
                    "AMActionVersion": "2.0.3",
                    "AMApplication": ["Automator"],
                    "AMParameterProperties": {
                        "COMMAND_STRING": {},
                        "CheckedForUserDefaultShell": {},
                        "inputMethod": {},
                        "shell": {},
                        "source": {},
                    },
                    "AMProvides": {
                        "Container": "List",
                        "Types": ["com.apple.cocoa.string"],
                    },
                    "ActionBundlePath": "/System/Library/Automator/Run Shell Script.action",
                    "ActionName": "Run Shell Script",
                    "ActionParameters": {
                        "COMMAND_STRING": command_str,
                        "CheckedForUserDefaultShell": True,
                        "inputMethod": 1,
                        "shell": "/bin/zsh",
                        "source": "",
                    },
                    "BundleIdentifier": "com.apple.RunShellScript",
                    "CFBundleVersion": "2.0.3",
                    "CanShowSelectedItemsWhenRun": False,
                    "CanShowWhenRun": True,
                    "Category": ["AMCategoryUtilities"],
                    "Class Name": "RunShellScriptAction",
                    "InputUUID": input_uuid,
                    "Keywords": ["Shell", "Script", "Command", "Run", "Unix"],
                    "OutputUUID": output_uuid,
                    "UUID": action_uuid,
                    "UnlocalizedApplications": ["Automator"],
                    "arguments": {
                        "0": {
                            "default value": 0,
                            "name": "inputMethod",
                            "required": "0",
                            "type": "0",
                            "uuid": "0",
                        },
                        "1": {
                            "default value": "",
                            "name": "source",
                            "required": "0",
                            "type": "0",
                            "uuid": "1",
                        },
                        "2": {
                            "default value": False,
                            "name": "CheckedForUserDefaultShell",
                            "required": "0",
                            "type": "0",
                            "uuid": "2",
                        },
                        "3": {
                            "default value": "",
                            "name": "COMMAND_STRING",
                            "required": "0",
                            "type": "0",
                            "uuid": "3",
                        },
                        "4": {
                            "default value": "/bin/sh",
                            "name": "shell",
                            "required": "0",
                            "type": "0",
                            "uuid": "4",
                        },
                    },
                    "isViewVisible": 1,
                },
                "isViewVisible": 1,
            }
        ],
        "connectors": {},
        "workflowMetaData": {
            "applicationBundleID": "com.apple.finder",
            "applicationBundleIDsByPath": {
                "/System/Library/CoreServices/Finder.app": "com.apple.finder"
            },
            "applicationPath": "/System/Library/CoreServices/Finder.app",
            "applicationPaths": ["/System/Library/CoreServices/Finder.app"],
            "inputTypeIdentifier": "com.apple.Automator.fileSystemObject.folder",
            "outputTypeIdentifier": "com.apple.Automator.nothing",
            "presentationMode": 15,
            "processesInput": 0,
            "serviceApplicationBundleID": "com.apple.finder",
            "serviceApplicationPath": "/System/Library/CoreServices/Finder.app",
            "serviceInputTypeIdentifier": "com.apple.Automator.fileSystemObject.folder",
            "serviceOutputTypeIdentifier": "com.apple.Automator.nothing",
            "serviceProcessesInput": 0,
            "systemImageName": "NSActionTemplate",
            "useAutomaticInputType": 0,
            "workflowTypeIdentifier": "com.apple.Automator.servicesMenu",
        },
    }
    with open(os.path.join(contents_dir, "document.wflow"), "wb") as f:
        plistlib.dump(document_wflow, f)

    pbs = "/System/Library/CoreServices/pbs"
    if os.path.exists(pbs):
        try:
            subprocess.run(
                [pbs, "-update"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            pass

    print(
        "Ação Rápida instalada no Finder (~/Library/Services).\n"
        "Clique com o botão direito em uma pasta -> Ações Rápidas (ou Serviços) -> Ver proporção de pastas."
    )
