# Container Processing UI Implementation Plan

## API Endpoints Identified

### 1. Command Management (`CommandRestApi.java`)
- `GET /xapi/commands` - List all available commands
- `GET /xapi/commands/{id}` - Get command details
- `GET /xapi/commands/available?project={project}&xsiType={xsiType}` - Get commands available for a specific context
- `GET /xapi/projects/{project}/commands/available?xsiType={xsiType}` - Project-scoped available commands

### 2. Command Configuration (`CommandConfigurationRestApi.java`)
- `GET /xapi/wrappers/{wrapperId}/config` - Get site configuration
- `GET /xapi/projects/{project}/wrappers/{wrapperId}/config` - Get project configuration
- `GET /xapi/projects/{project}/wrappers/{wrapperId}/enabled` - Check if wrapper is enabled

### 3. Launch Operations (`LaunchRestApi.java`)
- `GET /xapi/wrappers/{wrapperId}/launch?{params}` - Get launch UI/form definition
- `GET /xapi/projects/{project}/wrappers/{wrapperId}/launch?{params}` - Project-scoped launch UI
- `POST /xapi/wrappers/{wrapperId}/root/{rootElement}/launch` - Launch container (JSON body)
- `POST /xapi/projects/{project}/wrappers/{wrapperId}/root/{rootElement}/launch` - Project-scoped launch
- `POST /xapi/commands/{commandId}/wrappers/{wrapperName}/root/{rootElement}/bulklaunch` - Bulk launch

### 4. Container Management (`ContainerRestApi.java`)
- `GET /xapi/containers` - List all containers
- `GET /xapi/projects/{project}/containers` - List project containers
- `GET /xapi/containers/{id}` - Get container details
- `POST /xapi/containers/{id}/kill` - Kill a running container
- `GET /xapi/containers/{containerId}/logs` - Get container logs

## UI Component Architecture

### New Components to Create:

1. **`CommandLauncher.tsx`** - Main container launch interface
   - Select command/wrapper from available options
   - Browse by project or site-wide
   - View command details and requirements

2. **`LaunchForm.tsx`** - Dynamic form for launching containers
   - Fetch launch UI definition from API (`GET /xapi/.../launch`)
   - Dynamically render input fields based on wrapper configuration
   - Support for different input types (XNAT objects, files, parameters)
   - Validation before submission

3. **`CommandBrowser.tsx`** - Browse and search available commands
   - Filter by project, xsiType, availability
   - Display command metadata (image, version, inputs/outputs)
   - Enable/disable commands (admin)

4. **`ContainerMonitor.tsx`** - Enhanced container monitoring
   - Real-time status updates
   - Log streaming
   - Kill/control operations
   - Container resource usage

5. **`BulkLaunchWizard.tsx`** - Multi-step wizard for bulk launches
   - Select target objects (scans, sessions, subjects)
   - Configure common parameters
   - Review and confirm batch launch
   - Monitor batch progress

## Data Models (TypeScript Interfaces)

```typescript
// Command and Wrapper types
interface Command {
  id: number;
  name: string;
  image: string;
  version: string;
  description?: string;
  xnatCommandWrappers: CommandWrapper[];
}

interface CommandWrapper {
  id: number;
  name: string;
  description?: string;
  contexts: string[]; // xsiTypes this wrapper can run on
}

interface CommandSummaryForContext {
  commandId: number;
  commandName: string;
  wrapperId: number;
  wrapperName: string;
  wrapperDescription?: string;
  enabled: boolean;
}

// Launch UI Definition
interface LaunchUi {
  wrapperId: number;
  inputs: LaunchInput[];
  rootElement: string;
}

interface LaunchInput {
  name: string;
  label?: string;
  description?: string;
  type: 'string' | 'number' | 'boolean' | 'select' | 'xnat-object';
  required: boolean;
  defaultValue?: any;
  options?: { value: string; label: string }[];
}

// Launch Report
interface LaunchReport {
  status: 'Success' | 'Failure';
  containerId?: string;
  message?: string;
}

interface BulkLaunchReport {
  succeeded: LaunchReport[];
  failed: LaunchReport[];
}
```

## User Flows

### Flow 1: Launch Single Container
1. Navigate to Processing → Launch Container
2. Select project (optional) and data context (scan, session, subject)
3. Browse available commands for that context
4. Select command/wrapper
5. View command details and requirements
6. Fill launch form (auto-populated from context, user provides parameters)
7. Preview configuration
8. Launch container
9. Redirect to monitor view

### Flow 2: Bulk Launch
1. Navigate to data list (e.g., Scans page)
2. Select multiple items
3. Click "Run Processing" action
4. Select command/wrapper compatible with selected items
5. Configure shared parameters
6. Review launch matrix
7. Submit bulk launch
8. Monitor progress dashboard

### Flow 3: Monitor & Control
1. View running containers on Processing Dashboard
2. Click container for details
3. Stream logs in real-time
4. Kill/stop container if needed
5. View outputs when complete

### Flow 4: Command Administration (Admin only)
1. Navigate to Settings → Commands
2. Browse installed commands
3. Enable/disable for site or project
4. Configure wrapper settings
5. Test command with sample data

## Implementation Phases

### Phase 1: Core Infrastructure
- Add TypeScript interfaces for commands and launch types
- Extend XnatApiClient with container service methods
- Create basic CommandBrowser component

### Phase 2: Single Launch
- Create LaunchForm with dynamic field rendering
- Implement launch workflow
- Add to navigation

### Phase 3: Monitoring Enhancements
- Enhance existing Processing.tsx with kill/control actions
- Add log viewer modal
- Real-time updates

### Phase 4: Bulk Launch
- Create BulkLaunchWizard
- Integrate with data list pages (Scans, Experiments)
- Batch progress tracking

### Phase 5: Administration
- Command configuration UI (admin only)
- Enable/disable management
- Command testing interface

## Key Implementation Notes

1. **Dynamic Form Generation**: The `LaunchUi` API returns form definitions - need flexible rendering
2. **Context Awareness**: Commands are contextual (scan-level, session-level, etc.) - must pass correct `rootElement`
3. **Project Scoping**: Most endpoints have site and project variants - UI should default to project context when available
4. **Permissions**: Container Manager role required for config, Delete level for project launches
5. **Real-time Updates**: Container status changes rapidly - use polling or consider WebSocket for logs
6. **Bulk Operations**: `bulklaunch` endpoints support processing multiple objects - complex but powerful feature
