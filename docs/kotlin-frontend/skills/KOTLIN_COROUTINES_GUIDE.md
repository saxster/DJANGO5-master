# KOTLIN COROUTINES ERROR HANDLING GUIDE
## Async Programming Without Zombies, Crashes, or Leaks

**Version**: 1.0
**Last Updated**: October 30, 2025
**Based on**: Kotlin 1.9+, kotlinlang.org official docs, droidcon July 2025

---

## Table of Contents

1. [The CancellationException Rule](#1-the-cancellationexception-rule)
2. [Exception Propagation](#2-exception-propagation)
3. [Flow Error Handling](#3-flow-error-handling)
4. [Structured Concurrency](#4-structured-concurrency)
5. [Testing Coroutines](#5-testing-coroutines)
6. [Common Pitfalls](#6-common-pitfalls)

---

## 1. The CancellationException Rule

### 1.1 THE GOLDEN RULE ⚠️ CRITICAL

**CancellationException MUST ALWAYS BE RETHROWN**

**Why**: Swallowing CancellationException creates "zombie coroutines" - they keep running, doing no useful work, potentially holding resources forever.

```kotlin
// ❌ WRONG: Swallows CancellationException = ZOMBIE COROUTINE!
viewModelScope.launch {
    try {
        repository.getData()
    } catch (e: Exception) {
        // This catches CancellationException too!
        // Coroutine won't stop when ViewModel cleared
        _error.value = e.message
    }
}

// ✅ CORRECT Option A: Rethrow CancellationException
viewModelScope.launch {
    try {
        repository.getData()
    } catch (e: CancellationException) {
        throw e  // MUST rethrow!
    } catch (e: Exception) {
        _error.value = e.message
    }
}

// ✅ CORRECT Option B: Use Flow.catch {} (handles CancellationException correctly)
repository.getData()
    .catch { e ->
        // Flow.catch() doesn't catch CancellationException
        _error.value = e.message
    }
    .collect { data ->
        _data.value = data
    }

// ✅ CORRECT Option C: Check before handling
viewModelScope.launch {
    try {
        repository.getData()
    } catch (e: Exception) {
        if (e is CancellationException) {
            throw e  // Rethrow
        }
        _error.value = e.message
    }
}
```

**Source**: droidcon July 2025 - "Mastering Coroutine Cancellation"

---

### 1.2 Detecting Cancellation

```kotlin
// Check if coroutine is still active
suspend fun longRunningTask() {
    repeat(1000) { i ->
        // Check cancellation every iteration
        yield()  // or: ensureActive()

        // Do work
        processItem(i)
    }
}

// Alternative: ensureActive()
suspend fun longRunningTask() {
    repeat(1000) { i ->
        currentCoroutineContext().ensureActive()  // Throws if cancelled

        processItem(i)
    }
}
```

**When to Check**: Every loop iteration, before expensive operations

---

## 2. Exception Propagation

### 2.1 launch vs async

**launch**: Exceptions propagate to parent immediately

```kotlin
viewModelScope.launch {
    // Exception here cancels entire viewModelScope
    throw IOException("Network error")
}

// To handle:
viewModelScope.launch {
    try {
        dangerousOperation()
    } catch (e: IOException) {
        _error.value = e.message
    }
}
```

**async**: Exceptions stored until await() called

```kotlin
val deferred = viewModelScope.async {
    throw IOException("Network error")  // Stored, not thrown yet
}

// Exception thrown HERE when await() called
try {
    val result = deferred.await()  // Throws IOException
} catch (e: IOException) {
    _error.value = e.message
}
```

---

### 2.2 SupervisorJob vs Job

**Job**: One child fails → all children cancelled

```kotlin
val scope = CoroutineScope(Job())

scope.launch {
    // This fails
    throw IOException()
}

scope.launch {
    // This gets cancelled because sibling failed
    longRunningTask()
}
```

**SupervisorJob**: Children independent - one fails, others continue

```kotlin
val scope = CoroutineScope(SupervisorJob())

scope.launch {
    // This fails
    throw IOException()
}

scope.launch {
    // This continues running (sibling failure doesn't affect it)
    longRunningTask()
}
```

**Recommendation**: Use SupervisorJob for independent operations (like background sync)

---

### 2.3 CoroutineExceptionHandler

**Use for**: Logging uncaught exceptions in root coroutines

```kotlin
val exceptionHandler = CoroutineExceptionHandler { _, exception ->
    Log.e("CoroutineError", "Uncaught exception", exception)
    // Send to crash reporting
    crashlytics.recordException(exception)
}

val scope = CoroutineScope(SupervisorJob() + exceptionHandler)

scope.launch {
    throw IOException()  // Caught by handler, logged
}
```

**Important**: Cannot recover from exception - only for logging/reporting

---

## 3. Flow Error Handling

### 3.1 catch {} Operator (Recommended)

```kotlin
// ✅ BEST: Use Flow.catch {}
repository.getJournalEntries()
    .catch { e ->
        // Automatically doesn't catch CancellationException
        emit(Result.Error(e))
    }
    .collect { data ->
        _state.value = Result.Success(data)
    }
```

**Advantages**:
- Doesn't catch CancellationException (safe by default)
- Declarative (part of Flow chain)
- Can emit values on error

---

### 3.2 retry {} and retryWhen {}

```kotlin
// Retry on specific errors
repository.getJournalEntries()
    .retry(retries = 3) { cause ->
        // Only retry on network errors
        cause is IOException
    }
    .catch { e ->
        emit(Result.Error(e))
    }
    .collect { data ->
        _state.value = Result.Success(data)
    }

// Advanced: exponential backoff
repository.getJournalEntries()
    .retryWhen { cause, attempt ->
        if (cause is IOException && attempt < 3) {
            delay(2.0.pow(attempt.toDouble()).toLong() * 1000)  // Exponential
            true  // Retry
        } else {
            false  // Don't retry
        }
    }
    .collect { data ->
        _state.value = Result.Success(data)
    }
```

---

### 3.3 onCompletion {} vs catch {}

```kotlin
// catch {} - Handle upstream errors
flow {
    emit(1)
    throw IOException()  // Caught by catch {}
    emit(2)  // Never reached
}
    .catch { e ->
        emit(-1)  // Emit fallback value
    }
    .collect { println(it) }  // Prints: 1, -1

// onCompletion {} - Always executes (like finally)
flow {
    emit(1)
    throw IOException()
}
    .onCompletion { cause ->
        if (cause != null) {
            println("Flow failed: $cause")
        }
        // Cleanup here
    }
    .catch { /* Handle error */ }
    .collect { println(it) }
```

**Use onCompletion for**: Cleanup (close resources, reset state)
**Use catch for**: Error handling (emit fallback, show error)

---

## 4. Structured Concurrency

### 4.1 Scope Usage

**viewModelScope**: Cancelled when ViewModel cleared

```kotlin
class MyViewModel : ViewModel() {
    fun loadData() {
        viewModelScope.launch {  // Auto-cancelled on onCleared()
            repository.getData().collect { ... }
        }
    }
}
```

**lifecycleScope**: Cancelled when lifecycle destroyed

```kotlin
class MyFragment : Fragment() {
    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        lifecycleScope.launch {  // Cancelled when fragment destroyed
            viewModel.state.collect { ... }
        }
    }
}
```

**Custom scope**: You manage lifecycle

```kotlin
class MyWorker {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    fun doWork() {
        scope.launch { ... }
    }

    fun cleanup() {
        scope.cancel()  // MUST call manually!
    }
}
```

---

### 4.2 Avoid GlobalScope ⚠️

```kotlin
// ❌ WRONG: GlobalScope lives forever, no cancellation
GlobalScope.launch {
    repository.getData()  // Runs even after ViewModel/Activity destroyed
}

// ✅ CORRECT: Use appropriate scope
viewModelScope.launch {
    repository.getData()  // Cancelled when ViewModel cleared
}
```

**Only use GlobalScope for**: Application-level singletons (very rare)

---

## 5. Testing Coroutines

### 5.1 runTest (Latest API)

```kotlin
@Test
fun `repository emits data successfully`() = runTest {
    // Given
    val expected = listOf(entry1, entry2)
    coEvery { remoteDataSource.getAll() } returns expected

    // When
    val result = repository.getJournalEntries().first()

    // Then
    assertTrue(result is Result.Success)
    assertEquals(expected, (result as Result.Success).data)
}
```

**Benefit**: Skips delays (delay(1000) executes instantly in tests)

---

### 5.2 TestDispatcher

```kotlin
@OptIn(ExperimentalCoroutinesApi::class)
class MyViewModelTest {
    private val testDispatcher = UnconfinedTestDispatcher()

    @Before
    fun setup() {
        Dispatchers.setMain(testDispatcher)
    }

    @After
    fun teardown() {
        Dispatchers.resetMain()
    }

    @Test
    fun `loadData updates state`() = runTest {
        // Test executes immediately (no delays)
        viewModel.loadData()

        assertEquals(expected, viewModel.state.value)
    }
}
```

---

### 5.3 Testing Flows with Turbine

```kotlin
@Test
fun `repository emits loading then success`() = runTest {
    repository.getJournalEntries().test {
        // First emission
        val loading = awaitItem()
        assertTrue(loading is Result.Loading)

        // Second emission
        val success = awaitItem()
        assertTrue(success is Result.Success)

        // No more emissions
        awaitComplete()
    }
}
```

---

## 6. Common Pitfalls

### Pitfall 1: Zombie Coroutines

```kotlin
// ❌ CREATES ZOMBIES
class MyViewModel : ViewModel() {
    private val customScope = CoroutineScope(Dispatchers.IO)

    fun loadData() {
        customScope.launch {
            // Keeps running after ViewModel cleared!
            infiniteLoop()
        }
    }

    // No onCleared() to cancel customScope
}

// ✅ CORRECT: Use viewModelScope or cancel manually
class MyViewModel : ViewModel() {
    private val customScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    fun loadData() {
        customScope.launch { ... }
    }

    override fun onCleared() {
        super.onCleared()
        customScope.cancel()  // Clean up!
    }
}

// ✅ BETTER: Just use viewModelScope
class MyViewModel : ViewModel() {
    fun loadData() {
        viewModelScope.launch { ... }  // Auto-cancelled
    }
}
```

---

### Pitfall 2: Blocking Calls in Coroutines

```kotlin
// ❌ WRONG: Blocking call in coroutine
viewModelScope.launch {
    val data = database.getData()  // Blocks thread!
}

// ✅ CORRECT: Use suspend function
viewModelScope.launch {
    val data = database.getDataSuspend()  // Non-blocking
}

@Dao
interface MyDao {
    @Query("SELECT * FROM my_table")
    suspend fun getDataSuspend(): List<Data>  // Suspend function
}
```

---

### Pitfall 3: Infinite Retries

```kotlin
// ❌ WRONG: Retries forever
flow {
    emit(apiCall())
}
    .retry { true }  // INFINITE RETRIES!
    .collect { ... }

// ✅ CORRECT: Limit retries
flow {
    emit(apiCall())
}
    .retry(retries = 3) { cause ->
        cause is IOException  // Only retry network errors
    }
    .collect { ... }
```

---

## 7. Production Checklist

- [ ] All CancellationException rethrown
- [ ] No GlobalScope usage (except singletons)
- [ ] All custom scopes cancelled in cleanup
- [ ] Flow.catch {} used for error handling
- [ ] Retries limited (max 3-5 attempts)
- [ ] Structured concurrency maintained (parent-child relationships)
- [ ] Tests use runTest and TestDispatcher
- [ ] No blocking calls in coroutines (use suspend functions)

---

## Summary

This guide prevents **20+ async bugs**:

✅ CancellationException handling (prevents zombie coroutines)
✅ Exception propagation (launch vs async)
✅ Flow error handling (catch, retry, onCompletion)
✅ Structured concurrency (proper scope usage)
✅ Testing patterns (runTest, Turbine)
✅ Common pitfalls (zombies, blocking calls, infinite retries)

**Follow during Phase 4-8 implementation.**

---

**Document Version**: 1.0
**Based on**: kotlinlang.org, droidcon July 2025, Android official guidelines
**Prevents**: 20+ coroutine-related bugs
