# JETPACK COMPOSE BEST PRACTICES GUIDE
## Performance Optimization & State Management

**Version**: 1.0
**Last Updated**: October 30, 2025
**Based on**: Jetpack Compose 1.5+, droidcon October 2025, developer.android.com

---

## Table of Contents

1. [Recomposition Optimization](#1-recomposition-optimization)
2. [State Hoisting](#2-state-hoisting)
3. [Side Effects](#3-side-effects)
4. [Performance Patterns](#4-performance-patterns)
5. [Common Pitfalls](#5-common-pitfalls)

---

## 1. Recomposition Optimization

### 1.1 Defer State Reads with Lambdas ⭐

**Pattern**: Pass state access via lambda, not direct value

```kotlin
// ❌ WRONG: Reads state immediately, entire parent recomposes
@Composable
fun ParentScreen(count: Int) {  // Reads state.value here
    Column {
        Text("Count: $count")  // Parent recomposes when count changes
        OtherComponent()       // This also recomposes unnecessarily!
    }
}

// ✅ CORRECT: Lambda defers state read
@Composable
fun ParentScreen(count: () -> Int) {  // Lambda, not value
    Column {
        Text("Count: ${count()}")  // State read ONLY here
        OtherComponent()           // This doesn't recompose!
    }
}

// Usage
val count by viewModel.count.collectAsState()
ParentScreen(count = { count })  // Pass lambda
```

**Benefit**: Only Text recomposes, not entire Column. Can save 50-70% recompositions.

**Source**: droidcon October 2025 - "Reducing Unnecessary Recompositions"

---

### 1.2 derivedStateOf for Computed Values

```kotlin
// ❌ WRONG: Recomputes every recomposition
@Composable
fun MyList(items: List<Item>) {
    val filteredItems = items.filter { it.isActive }  // Recomputed every time!

    LazyColumn {
        items(filteredItems) { ... }
    }
}

// ✅ CORRECT: Use derivedStateOf
@Composable
fun MyList(items: List<Item>) {
    val filteredItems by remember(items) {
        derivedStateOf {
            items.filter { it.isActive }  // Only recomputed when items change
        }
    }

    LazyColumn {
        items(filteredItems) { ... }
    }
}
```

**When to Use**: Expensive computations based on state

---

### 1.3 Stable Types (@Stable, @Immutable)

```kotlin
// ❌ UNSTABLE: Compose can't verify immutability
data class UiState(
    val entries: List<JournalEntry>,
    var isLoading: Boolean  // var makes it mutable = unstable!
)

// ✅ STABLE: All properties val (immutable)
@Immutable
data class UiState(
    val entries: List<JournalEntry>,
    val isLoading: Boolean
)

// ✅ STABLE: Immutable data class
@Immutable
data class JournalEntry(
    val id: String,
    val title: String,
    val moodRating: Int?
)
```

**Rule**: If Compose can't prove a type is stable, it assumes it's unstable → more recompositions

**Mark as @Stable when**: Type is effectively immutable (even if Compose can't prove it)

---

### 1.4 Keys in LazyColumn/Row

```kotlin
// ❌ WRONG: No keys, Compose can't track items efficiently
LazyColumn {
    items(entries) { entry ->
        JournalEntryCard(entry)  // Recomposes all items on any change
    }
}

// ✅ CORRECT: Provide stable keys
LazyColumn {
    items(
        items = entries,
        key = { entry -> entry.id }  // Stable key
    ) { entry ->
        JournalEntryCard(entry)  // Only changed items recompose
    }
}
```

**Benefit**: Item moves in list → doesn't recompose, just repositions. Much faster.

---

## 2. State Hoisting

### 2.1 When to Hoist State

**Hoist when**:
- State needs to be shared between components
- State needs to persist across recompositions
- Parent needs to control child state

**Keep local when**:
- State only used within component
- State is UI-only (not business logic)
- No need to test state in isolation

```kotlin
// ✅ LOCAL STATE: Only used within component
@Composable
fun SearchBar() {
    var query by remember { mutableStateOf("") }  // Local

    TextField(
        value = query,
        onValueChange = { query = it }
    )
}

// ✅ HOISTED STATE: Parent needs to know
@Composable
fun SearchScreen(
    onSearch: (String) -> Unit
) {
    var query by remember { mutableStateOf("") }  // Hoisted to parent

    SearchBar(
        query = query,
        onQueryChange = { query = it },
        onSearch = { onSearch(query) }
    )
}

@Composable
fun SearchBar(
    query: String,
    onQueryChange: (String) -> Unit,
    onSearch: () -> Unit
) {
    TextField(
        value = query,
        onValueChange = onQueryChange
    )
}
```

---

### 2.2 remember vs rememberSaveable

```kotlin
// remember: Survives recomposition, lost on config change (rotation)
var count by remember { mutableStateOf(0) }

// rememberSaveable: Survives recomposition AND config changes
var count by rememberSaveable { mutableStateOf(0) }
```

**Use rememberSaveable for**: User input, scroll position, expanded states

---

## 3. Side Effects

### 3.1 LaunchedEffect (Run Coroutine on Key Change)

```kotlin
@Composable
fun MyScreen(userId: Int) {
    LaunchedEffect(userId) {  // Runs when userId changes
        viewModel.loadUserData(userId)
    }

    // If userId changes, previous coroutine cancelled, new one launched
}

// Common pattern: Collect Flow
@Composable
fun MyScreen(viewModel: MyViewModel) {
    LaunchedEffect(Unit) {  // Runs once (Unit never changes)
        viewModel.events.collect { event ->
            when (event) {
                is NavigateToDetail -> navController.navigate(...)
            }
        }
    }
}
```

**Keys**: Change keys → coroutine restarts

---

### 3.2 DisposableEffect (Cleanup Resources)

```kotlin
@Composable
fun LocationTracker() {
    DisposableEffect(Unit) {
        // Register listener
        val listener = locationManager.requestLocationUpdates(...)

        onDispose {
            // Cleanup when leaving composition
            locationManager.removeUpdates(listener)
        }
    }
}
```

**Use for**: Registering/unregistering listeners, opening/closing resources

---

### 3.3 SideEffect (Synchronize Compose State with Non-Compose)

```kotlin
@Composable
fun MyScreen(selectedId: String) {
    val analytics = LocalAnalytics.current

    SideEffect {
        // Runs after every successful recomposition
        analytics.logScreenView(selectedId)
    }
}
```

**Use for**: Updating non-Compose objects that need to stay in sync

---

## 4. Performance Patterns

### 4.1 Avoid Creating Lambdas on Recomposition

```kotlin
// ❌ WRONG: New lambda every recomposition
@Composable
fun MyList(items: List<Item>, viewModel: MyViewModel) {
    LazyColumn {
        items(items) { item ->
            ItemCard(
                item = item,
                onClick = { viewModel.onItemClick(item.id) }  // New lambda!
            )
        }
    }
}

// ✅ CORRECT: Stable callback from parent
@Composable
fun MyList(
    items: List<Item>,
    onItemClick: (String) -> Unit  // Passed from parent, stable
) {
    LazyColumn {
        items(items, key = { it.id }) { item ->
            ItemCard(
                item = item,
                onClick = { onItemClick(item.id) }  // Stable
            )
        }
    }
}
```

---

### 4.2 Heavy Computation in remember {}

```kotlin
// ❌ WRONG: Heavy computation on every recomposition
@Composable
fun MyScreen(data: List<Data>) {
    val processed = data.map { heavyProcessing(it) }  // Runs every recomposition!
}

// ✅ CORRECT: Cache in remember {}
@Composable
fun MyScreen(data: List<Data>) {
    val processed = remember(data) {
        data.map { heavyProcessing(it) }  // Only when data changes
    }
}
```

---

### 4.3 Modifier.offset {} for Animations

```kotlin
// ❌ SLOW: Creates new modifier every frame
@Composable
fun AnimatedBox(offset: Float) {
    Box(
        Modifier.offset(x = offset.dp)  // New modifier every frame!
    )
}

// ✅ FAST: Lambda-based modifier
@Composable
fun AnimatedBox(offset: Float) {
    Box(
        Modifier.offset { IntOffset(offset.roundToInt(), 0) }  // Lambda version
    )
}
```

**Use for**: Rapidly changing values (animations, scroll position)

---

## 5. Common Pitfalls

### Pitfall 1: ViewModel in Composable (Not in Screen)

```kotlin
// ❌ WRONG: ViewModel created in reusable component
@Composable
fun JournalEntryCard(entry: JournalEntry) {
    val viewModel: EntryViewModel = hiltViewModel()  // New ViewModel per card!
    // ...
}

// ✅ CORRECT: ViewModel in screen, pass data to components
@Composable
fun JournalListScreen(
    viewModel: JournalListViewModel = hiltViewModel()  // One ViewModel for screen
) {
    val entries by viewModel.entries.collectAsState()

    LazyColumn {
        items(entries) { entry ->
            JournalEntryCard(
                entry = entry,  // Pass data, not ViewModel
                onClick = { viewModel.onEntryClick(entry.id) }
            )
        }
    }
}

@Composable
fun JournalEntryCard(
    entry: JournalEntry,  // Data, not ViewModel
    onClick: () -> Unit
) {
    // Pure UI component
}
```

---

### Pitfall 2: Not Using keys() for Different Content

```kotlin
// ❌ WRONG: Compose can't distinguish different branches
@Composable
fun MyScreen(isLoggedIn: Boolean) {
    if (isLoggedIn) {
        LoggedInContent()  // Compose might reuse state from LoggedOutContent!
    } else {
        LoggedOutContent()
    }
}

// ✅ CORRECT: Use key() to distinguish
@Composable
fun MyScreen(isLoggedIn: Boolean) {
    if (isLoggedIn) {
        key("logged_in") {
            LoggedInContent()  // Separate identity
        }
    } else {
        key("logged_out") {
            LoggedOutContent()  // Separate identity
        }
    }
}
```

---

## Summary

This guide prevents **15+ UI performance issues**:

✅ Recomposition optimization (defer state reads, derivedStateOf)
✅ Stable types (@Immutable for data classes)
✅ Lazy layout keys (efficient list updates)
✅ State hoisting (when and where)
✅ Side effects (LaunchedEffect, DisposableEffect, SideEffect)
✅ Performance patterns (lambda modifiers, remember for heavy computation)
✅ Common pitfalls (ViewModel placement, lambda creation, missing keys)

**Follow during Phase 5 implementation.**

---

**Document Version**: 1.0
**Based on**: developer.android.com, droidcon October 2025
**Prevents**: 15+ Compose performance issues
